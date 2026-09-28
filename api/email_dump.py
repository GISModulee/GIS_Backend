from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database.database import get_db
from schemas.email_dump_schema import (
    EmailDumpDumpsQuery,
    EmailDumpListResponse,
    EmailDumpOriginIpImportResponse,
    EmailDumpOriginIpQuery,
    EmailDumpTargetsResponse,
)
from services.email_dump.dumps import list_dumps, list_targets
from services.email_dump.origin_ips import import_origin_ips
from utils.constants import STATUS_OK
from utils.dependencies import get_access_token, require_roles_for_case
from utils.logger import logger
from utils.roles import CAN_WRITE


router = APIRouter(tags=["Email Dump"])


# ===================================================
# EMAIL DUMP ORIGIN IPS
# ===================================================
# Frontend -> GIS Backend -> Email Dump Backend. The frontend never
# calls the Email Dump Backend directly: this route is the only entry
# point, it forwards the caller's bearer token upstream, and it returns
# a GIS-specific summary of the layers and features it persisted.
#
# Write access is required because the import creates layers and
# features, exactly like the other persisting routes.

@router.get(
    "/cases/{case_id}/email-dump/origin-ips",
    response_model=EmailDumpOriginIpImportResponse,
    status_code=STATUS_OK,
    summary="Import Email Dump origin IPs as GIS layers and features",
)
async def get_email_dump_origin_ips(
    case_id: int,
    view_type: str | None = Query(default=None, description="Email Dump view scope"),
    target_id: str | None = Query(default=None, description="Email Dump target identifier"),
    dump_id: str | None = Query(default=None, description="Email Dump identifier"),
    ip_type: str | None = Query(default=None, description="Filter by IP type"),
    limit: int | None = Query(default=None, ge=1, description="Maximum provider results"),
    keyword: str | None = Query(default=None, description="Free-text keyword filter"),
    isp: str | None = Query(default=None, description="Filter by ISP"),
    country: str | None = Query(default=None, description="Filter by country"),
    risk_level: str | None = Query(default=None, description="Filter by risk level"),
    is_suspicious: bool | None = Query(default=None, description="Filter by suspicious flag"),
    db: Session = Depends(get_db),
    access_token: str = Depends(get_access_token),
    current_user=Depends(require_roles_for_case(CAN_WRITE)),
) -> EmailDumpOriginIpImportResponse:
    """Fetch origin IPs for a case from Email Dump and store them in GIS."""
    query = EmailDumpOriginIpQuery(
        view_type=view_type,
        target_id=target_id,
        dump_id=dump_id,
        ip_type=ip_type,
        limit=limit,
        keyword=keyword,
        isp=isp,
        country=country,
        risk_level=risk_level,
        is_suspicious=is_suspicious,
    )

    logger.info(
        "GET /cases/%s/email-dump/origin-ips | user_id=%s | role=%s | filters=%s",
        case_id,
        current_user["user_id"],
        current_user["role"],
        query.to_forward_params(),
    )

    return await import_origin_ips(
        case_id,
        query,
        access_token,
        db,
        created_by=current_user["user_id"],
    )


@router.get(
    "/cases/{case_id}/email-dump/targets",
    response_model=EmailDumpTargetsResponse,
    status_code=STATUS_OK,
    summary="List the Email Dump targets in a case",
)
async def get_email_dump_targets(
    case_id: int,
    db: Session = Depends(get_db),
    access_token: str = Depends(get_access_token),
    current_user=Depends(require_roles_for_case(CAN_WRITE)),
) -> EmailDumpTargetsResponse:
    """List the targets Email Dump knows about for a case.

    This is what populates the target list. Each target already carries
    its `dump_ids`, so a frontend can build a dump dropdown from this
    response alone and only needs the dumps route when it needs a dump's
    counters.
    """
    logger.info(
        "GET /cases/%s/email-dump/targets | user_id=%s | role=%s",
        case_id,
        current_user["user_id"],
        current_user["role"],
    )

    return await list_targets(case_id, access_token, db)


# ===================================================
# EMAIL DUMP DUMPS
# ===================================================
# Same proxy shape as the import above, but read-oriented: the frontend
# calls it when the user picks a target, to fill the dump dropdown.
#
# The same CAN_WRITE gate applies. Targets are only ever shown for a case
# the user can write to, since both this route and the import above are
# gated the same way.

@router.get(
    "/cases/{case_id}/email-dump/dumps",
    response_model=EmailDumpListResponse,
    status_code=STATUS_OK,
    summary="List the Email Dump dumps available for a target",
)
async def get_email_dump_dumps(
    case_id: int,
    target_id: str = Query(description="Email Dump target identifier"),
    db: Session = Depends(get_db),
    access_token: str = Depends(get_access_token),
    current_user=Depends(require_roles_for_case(CAN_WRITE)),
) -> EmailDumpListResponse:
    """Fetch and cache the dumps belonging to one Email Dump target."""
    query = EmailDumpDumpsQuery(target_id=target_id)

    logger.info(
        "GET /cases/%s/email-dump/dumps | user_id=%s | role=%s | target_id=%s",
        case_id,
        current_user["user_id"],
        current_user["role"],
        query.target_id,
    )

    return await list_dumps(case_id, query.target_id, access_token, db)

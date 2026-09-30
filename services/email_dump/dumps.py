from typing import Any

import asyncio
import httpx
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from models.model import EmailDump, EmailTarget
from schemas.email_dump_schema import (
    EmailDumpListResponse,
    EmailDumpRef,
    EmailDumpTargetsResponse,
    EmailTargetSummary,
    _optional_datetime,
    _optional_int,
)
from utils.config import settings
from utils.constants import (
    EMAIL_DUMP_DUMPS_FETCH_FAILED,
    EMAIL_DUMP_DUMPS_PATH,
    EMAIL_DUMP_INVALID_DUMPS_RESPONSE,
    EMAIL_DUMP_INVALID_TARGETS_RESPONSE,
    EMAIL_DUMP_NOT_CONFIGURED,
    EMAIL_DUMP_RATE_LIMITED,
    EMAIL_DUMP_TARGETS_PREFIX_PATH,
    EMAIL_DUMP_TARGETS_FETCH_FAILED,
    EMAIL_DUMP_TARGET_NOT_FOUND,
    EMAIL_DUMP_TIMEOUT,
    EMAIL_DUMP_UNAUTHORIZED,
    EMAIL_DUMP_UNAVAILABLE,
    STATUS_FORBIDDEN,
    STATUS_NOT_FOUND,
    STATUS_TOO_MANY_REQUESTS,
    STATUS_UNAUTHORIZED,
)
from utils.exceptions import (
    AppException,
    GatewayTimeoutError,
    NotFoundError,
    ServiceUnavailableError,
    UnauthorizedError,
)
from utils.logger import logger


def _base_url() -> str:
    base_url = (settings.EMAIL_DUMP_API_BASE_URL or "").strip().rstrip("/")
    if not base_url:
        logger.error("Email Dump base URL is not configured")
        raise ServiceUnavailableError(EMAIL_DUMP_NOT_CONFIGURED)
    return base_url


def build_dumps_url(case_id: int) -> str:
    return f"{_base_url()}{EMAIL_DUMP_DUMPS_PATH}/{case_id}"


def build_targets_url(case_id: int) -> str:
    return f"{_base_url()}{EMAIL_DUMP_TARGETS_PREFIX_PATH}/{case_id}/targets"


def _provider_error(status_code: int) -> AppException:
    if status_code in (STATUS_UNAUTHORIZED, STATUS_FORBIDDEN):
        return UnauthorizedError(EMAIL_DUMP_UNAUTHORIZED)
    if status_code == STATUS_NOT_FOUND:
        return NotFoundError(EMAIL_DUMP_TARGET_NOT_FOUND)
    return ServiceUnavailableError(
        EMAIL_DUMP_RATE_LIMITED
        if status_code == STATUS_TOO_MANY_REQUESTS
        else EMAIL_DUMP_UNAVAILABLE
    )


def _normalise(item: dict) -> EmailDumpRef | None:
    dump_id = item.get("dump_id")
    if dump_id is None or isinstance(dump_id, (dict, list, bool)):
        return None
    dump_id = str(dump_id).strip()
    if not dump_id:
        return None

    return EmailDumpRef(
        dump_id=dump_id,
        name=item.get("name") if isinstance(item.get("name"), str) else None,
        total_emails=_optional_int(item.get("total_emails")),
        malicious_count=_optional_int(item.get("malicious_count")),
        unique_senders=_optional_int(item.get("unique_senders")),
        unique_recipients=_optional_int(item.get("unique_recipients")),
        start_date=_optional_datetime(item.get("start_date")),
        end_date=_optional_datetime(item.get("end_date")),
        created_at=_optional_datetime(item.get("created_at")),
    )


async def _get(
    url: str,
    case_id: int,
    target_id: str | None,
    access_token: str,
    invalid_message: str,
) -> Any:
    params = {"target_id": target_id} if target_id is not None else None

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(settings.EMAIL_DUMP_TIMEOUT_SECONDS)
        ) as client:
            response = await client.get(
                url,
                params=params,
                headers={"Authorization": f"Bearer {access_token}"},
            )
    except httpx.TimeoutException as exc:
        logger.warning(
            "Email Dump request timed out | url=%s | error=%s", url, exc
        )
        raise GatewayTimeoutError(EMAIL_DUMP_TIMEOUT) from exc
    except httpx.RequestError as exc:
        logger.warning(
            "Email Dump request failed | url=%s | error=%s", url, type(exc).__name__
        )
        raise ServiceUnavailableError(EMAIL_DUMP_UNAVAILABLE) from exc

    if response.status_code != 200:
        logger.warning(
            "Email Dump returned an error | url=%s | target_id=%s | status=%s",
            url,
            target_id,
            response.status_code,
        )
        raise _provider_error(response.status_code)

    try:
        return response.json()
    except ValueError as exc:
        logger.warning("Email Dump returned malformed JSON | url=%s", url)
        raise ServiceUnavailableError(invalid_message) from exc


def _extract_list(payload: Any, message: str, case_id: int, what: str) -> list[dict]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        return [item for item in payload["data"] if isinstance(item, dict)]

    observed = sorted(payload) if isinstance(payload, dict) else type(payload).__name__
    logger.warning(
        "Email Dump %s payload had no usable data list | case_id=%s | keys=%s",
        what,
        case_id,
        observed,
    )
    raise ServiceUnavailableError(message)


async def fetch_targets(
    case_id: int,
    access_token: str,
) -> list[EmailTargetSummary]:
    url = build_targets_url(case_id)
    payload = await _get(
        url,
        case_id,
        target_id=None,
        access_token=access_token,
        invalid_message=EMAIL_DUMP_INVALID_TARGETS_RESPONSE,
    )
    items = _extract_list(
        payload, EMAIL_DUMP_INVALID_TARGETS_RESPONSE, case_id, "targets"
    )

    targets: list[EmailTargetSummary] = []
    for item in items:
        target_id = _optional_int(item.get("target_id"))
        target_email = item.get("target_email")
        if target_id is None or not isinstance(target_email, str):
            logger.warning(
                "Email Dump target entry missing target_id/target_email, skipping | case_id=%s",
                case_id,
            )
            continue

        dump_ids = [
            str(value)
            for value in (item.get("dump_ids") or [])
            if isinstance(value, (str, int)) and not isinstance(value, bool)
        ]
        raw_statuses = item.get("dump_statuses")
        statuses = (
            {str(k): str(v) for k, v in raw_statuses.items()}
            if isinstance(raw_statuses, dict)
            else {}
        )

        targets.append(
            EmailTargetSummary(
                target_id=target_id,
                target_email=target_email,
                dump_count=_optional_int(item.get("dump_count")) or len(dump_ids),
                dump_ids=dump_ids,
                dump_statuses=statuses,
                report_id=_optional_int(item.get("report_id")),
            )
        )

    logger.info("Email Dump targets fetched | case_id=%s | targets=%s", case_id, len(targets))
    return targets


def _persist_targets(
    case_id: int,
    targets: list[EmailTargetSummary],
    db,
) -> tuple[int, int]:
    created = 0
    updated = 0

    try:
        existing = {
            (row.case_id, row.target_id): row
            for row in db.scalars(
                select(EmailTarget).where(EmailTarget.case_id == case_id)
            ).all()
        }

        for target in targets:
            target_id = str(target.target_id)
            row = existing.get((case_id, target_id))
            if row is None:
                db.add(
                    EmailTarget(
                        case_id=case_id,
                        target_id=target_id,
                        target_name=target.target_email,
                    )
                )
                created += 1
            elif row.target_name is None:
                row.target_name = target.target_email
                updated += 1

        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error(
            "Email Dump targets cache write failed | case_id=%s | error=%s",
            case_id,
            exc,
            exc_info=True,
        )
        raise ServiceUnavailableError(EMAIL_DUMP_TARGETS_FETCH_FAILED) from exc

    return created, updated


async def list_targets(
    case_id: int,
    access_token: str,
    db,
) -> EmailDumpTargetsResponse:
    targets = await fetch_targets(case_id, access_token)
    created, updated = _persist_targets(case_id, targets, db)

    if created or updated:
        logger.info(
            "Email Dump targets stored | case_id=%s | created=%s | updated=%s",
            case_id,
            created,
            updated,
        )

    return EmailDumpTargetsResponse(
        case_id=case_id,
        targets=targets,
        targets_count=len(targets),
    )


async def fetch_dumps(
    case_id: int,
    target_id: str,
    access_token: str,
) -> list[EmailDumpRef]:
    url = build_dumps_url(case_id)
    payload = await _get(
        url,
        case_id,
        target_id=target_id or None,
        access_token=access_token,
        invalid_message=EMAIL_DUMP_INVALID_DUMPS_RESPONSE,
    )
    items = _extract_list(payload, EMAIL_DUMP_INVALID_DUMPS_RESPONSE, case_id, "dumps")

    dumps: list[EmailDumpRef] = []
    for item in items:
        normalised = _normalise(item)
        if normalised is not None:
            dumps.append(normalised)

    logger.info(
        "Email Dump dumps fetched | case_id=%s | target_id=%s | dumps=%s",
        case_id,
        target_id,
        len(dumps),
    )
    return dumps


def resolve_target_row(
    case_id: int,
    target_id: str,
    db,
) -> EmailTarget | None:
    try:
        row = db.scalar(
            select(EmailTarget).where(
                EmailTarget.case_id == case_id,
                EmailTarget.target_id == str(target_id),
            )
        )
    except SQLAlchemyError as exc:
        logger.error(
            "Email Dump target lookup failed | case_id=%s | target_id=%s | error=%s",
            case_id,
            target_id,
            exc,
            exc_info=True,
        )
        raise ServiceUnavailableError(EMAIL_DUMP_DUMPS_FETCH_FAILED) from exc

    if row is None:
        logger.info(
            "Email Dump target has not been imported for this case | case_id=%s | target_id=%s",
            case_id,
            target_id,
        )
    return row


def _cached_dumps(case_id: int, target_id: str, db) -> list[EmailDumpRef]:
    try:
        rows = db.scalars(
            select(EmailDump)
            .where(
                EmailDump.case_id == case_id,
                EmailDump.target_id == str(target_id),
            )
            .order_by(EmailDump.dump_id)
        ).all()
    except SQLAlchemyError as exc:
        logger.error(
            "Email Dump cached dumps lookup failed | case_id=%s | target_id=%s | error=%s",
            case_id,
            target_id,
            exc,
            exc_info=True,
        )
        raise ServiceUnavailableError(EMAIL_DUMP_DUMPS_FETCH_FAILED) from exc

    return [
        EmailDumpRef(
            dump_id=row.dump_id,
            name=row.name,
            total_emails=row.total_emails,
            malicious_count=row.malicious_count,
            unique_senders=row.unique_senders,
            unique_recipients=row.unique_recipients,
            start_date=row.start_date,
            end_date=row.end_date,
            created_at=row.provider_created_at,
        )
        for row in rows
    ]


def _cache_dumps(
    case_id: int,
    target_id: str,
    dumps: list[EmailDumpRef],
    db,
) -> tuple[int, int]:
    created = 0
    updated = 0

    def _values(dump: EmailDumpRef) -> dict:
        return {
            "name": dump.name,
            "total_emails": dump.total_emails,
            "malicious_count": dump.malicious_count,
            "unique_senders": dump.unique_senders,
            "unique_recipients": dump.unique_recipients,
            "start_date": dump.start_date,
            "end_date": dump.end_date,
            "provider_created_at": dump.created_at,
        }

    try:
        existing = {
            row.dump_id: row
            for row in db.scalars(
                select(EmailDump).where(
                    EmailDump.case_id == case_id,
                    EmailDump.target_id == str(target_id),
                )
            ).all()
        }

        for dump in dumps:
            values = _values(dump)
            row = existing.get(dump.dump_id)
            if row is None:
                db.add(
                    EmailDump(
                        case_id=case_id,
                        target_id=str(target_id),
                        dump_id=str(dump.dump_id),
                        **values,
                    )
                )
                created += 1
            else:
                changed = False
                for field, value in values.items():
                    if value is None:
                        continue
                    if getattr(row, field) != value:
                        setattr(row, field, value)
                        changed = True
                if changed:
                    updated += 1

        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error(
            "Email Dump dumps cache write failed | case_id=%s | target_id=%s | error=%s",
            case_id,
            target_id,
            exc,
            exc_info=True,
        )
        raise ServiceUnavailableError(EMAIL_DUMP_DUMPS_FETCH_FAILED) from exc

    return created, updated


async def _dumps_for_one_target(
    case_id: int,
    target_id: str,
    access_token: str,
    db,
) -> tuple[list[EmailDumpRef], int, int, bool]:
    target_row = resolve_target_row(case_id, target_id, db)

    dumps = await fetch_dumps(case_id, target_id, access_token)

    if target_row is None:
        logger.info(
            "Email Dump dumps not cached, target not imported | case_id=%s | target_id=%s",
            case_id,
            target_id,
        )
        return dumps, 0, 0, False

    created, updated = _cache_dumps(case_id, target_id, dumps, db)

    if not dumps:
        cached = _cached_dumps(case_id, target_id, db)
        if cached:
            logger.info(
                "Email Dump returned no dumps, serving cached list | case_id=%s | target_id=%s",
                case_id,
                target_id,
            )
            return cached, 0, 0, True

    return dumps, created, updated, False


async def list_dumps(
    case_id: int,
    target_ids: list[str],
    access_token: str,
    db,
) -> EmailDumpListResponse:
    results = await asyncio.gather(
        *(
            _dumps_for_one_target(case_id, target_id, access_token, db)
            for target_id in target_ids
        ),
        return_exceptions=True,
    )

    merged: list[EmailDumpRef] = []
    seen: set[str] = set()
    created = 0
    updated = 0
    served_from_cache = False
    failed: list[tuple[str, BaseException]] = []

    for target_id, result in zip(target_ids, results):
        if isinstance(result, BaseException):
            failed.append((target_id, result))
            continue

        dumps, target_created, target_updated, from_cache = result
        created += target_created
        updated += target_updated
        served_from_cache = served_from_cache or from_cache

        for dump in dumps:
            key = str(dump.dump_id)
            if key in seen:
                continue
            seen.add(key)
            merged.append(dump)

    if failed:
        _log_target_failures(case_id, failed, len(target_ids))

    if failed and len(failed) == len(target_ids):
        raise failed[0][1]

    return EmailDumpListResponse(
        case_id=case_id,
        target_ids=list(target_ids),
        dumps=merged,
        dumps_created=created,
        dumps_updated=updated,
        from_cache=served_from_cache,
    )


def _log_target_failures(
    case_id: int,
    failed: list[tuple[str, BaseException]],
    requested: int,
) -> None:
    ids = ", ".join(target_id for target_id, _ in failed)
    level = logger.error if len(failed) == requested else logger.warning
    level(
        "Email Dump could not list dumps for %s of %s target(s) | case_id=%s | "
        "target_ids=%s | errors=%s",
        len(failed),
        requested,
        case_id,
        ids,
        "; ".join(f"{target_id}: {exc}" for target_id, exc in failed),
    )
    for target_id, exc in failed:
        logger.debug(
            "Email Dump target listing failed | case_id=%s | target_id=%s",
            case_id,
            target_id,
            exc_info=exc,
        )

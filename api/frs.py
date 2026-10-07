from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database.database import get_db
from schemas.frs_schema import (
    FrsCameraRegistryResponse,
    FrsPersonHistoryImportResponse,
    FrsPersonRouteResponse,
    FrsPersonsResponse,
)
from services.frs import (
    import_person_history,
    fetch_persons,
    person_route,
    read_camera_registry,
    upsert_persons,
)
from utils.constants import STATUS_OK
from utils.dependencies import (
    authorize_case,
    enforce_role,
    get_access_token,
    require_roles,
    require_roles_for_case,
)
from utils.logger import logger
from utils.roles import ALL_ROLES, CAN_WRITE


router = APIRouter(tags=["Face Recognition System"])


@router.get(
    "/face-recognition-system/cameras",
    response_model=FrsCameraRegistryResponse,
    status_code=STATUS_OK,
    summary="Sync the FRS camera registry and draw its cameras",
)
async def get_frs_cameras(
    case_id: int | None = Query(
        default=None,
        description=(
            "Case to draw the cameras into. Omit it and the route only "
            "syncs the global registry and returns its stored rows, which "
            "carry the lat/long the frontend plots. Supply it and the "
            "route additionally imports one layer and one point feature "
            "per camera into that case, so the pins appear on the case "
            "map. A supplied case_id is validated for access and requires "
            "the write role, exactly as the old case-scoped cameras route "
            "did."
        ),
    ),
    db: Session = Depends(get_db),
    access_token: str = Depends(get_access_token),
    current_user=Depends(require_roles(ALL_ROLES)),
) -> FrsCameraRegistryResponse:
    """Sync the global FRS camera registry and return it, drawing if asked.

    The one cameras route: no case_id in the path, because the provider's
    registry is global — it owns one camera list and sends no case
    filter. Every call fetches from FRS, upserts `frs_cameras` and
    returns the stored rows (cameras the provider stopped reporting
    included, since the registry is never pruned). Those rows carry the
    camera latitude and longitude the frontend draws its pins from.

    Passing `?case_id=` additionally runs the case-scoped import: one
    layer per camera, one point feature at its reported fix, idempotent
    so re-opening the panel does not churn every open map, with
    withdrawn cameras keeping their layers and analyst comments. The
    counts come back in the same response.

    Base gate is `require_roles(ALL_ROLES)` — a valid token is still
    required, and with no case in the path there is no case membership
    to check for the read. When `case_id` IS supplied the old route's
    gate is applied in full before anything is written:
    `authorize_case` (token + case access) followed by
    `require_roles_for_case`'s CAN_WRITE check. The caller's own token is
    forwarded to FRS either way, which authenticates it independently;
    GIS stores no provider credential.
    """
    created_by = None
    if case_id is not None:
        case_user = await authorize_case(access_token, case_id)
        enforce_role(case_user, CAN_WRITE)
        created_by = case_user["user_id"]

    logger.info(
        "GET /face-recognition-system/cameras | user_id=%s | role=%s | case_id=%s",
        current_user["user_id"],
        current_user["role"],
        case_id,
    )

    return await read_camera_registry(
        access_token, db, case_id=case_id, created_by=created_by
    )


@router.get(
    "/cases/{case_id}/face-recognition-system/persons",
    response_model=FrsPersonsResponse,
    status_code=STATUS_OK,
    summary="List the FRS persons registered to a case",
)
async def get_frs_persons(
    case_id: int,
    db: Session = Depends(get_db),
    access_token: str = Depends(get_access_token),
    current_user=Depends(require_roles_for_case(CAN_WRITE)),
) -> FrsPersonsResponse:
    """List the persons FRS holds for this case, syncing the registry.

    A sync-on-read proxy: every list fetch also upserts every listed
    person into `frs_persons`, so anyone the case knows about gets a row
    whether or not their history has ever been pulled. This is what lets
    the route endpoint answer a person with no detections as an empty
    route instead of treating them as "never imported". Idempotent: re-
    opening the picker only updates a name/organization when the provider
    changed it, and never touches `layer_id`.

    The write role is still required. Person registry membership is
    investigative data — who a case knows about — so the same gate as
    the import routes applies.
    """
    logger.info(
        "GET /cases/%s/face-recognition-system/persons | user_id=%s | role=%s",
        case_id,
        current_user["user_id"],
        current_user["role"],
    )

    persons = await fetch_persons(case_id, access_token)
    created, updated = upsert_persons(case_id, persons, db)
    if created or updated:
        logger.info(
            "FRS persons registry synced | case_id=%s | persons=%s | "
            "created=%s | updated=%s",
            case_id,
            len(persons),
            created,
            updated,
        )
    return FrsPersonsResponse(case_id=case_id, persons=persons)


@router.get(
    "/cases/{case_id}/face-recognition-system/persons/{person_id}/history",
    response_model=FrsPersonHistoryImportResponse,
    status_code=STATUS_OK,
    summary="Import one person's FRS sighting history as GIS features",
)
async def get_frs_person_history(
    case_id: int,
    person_id: int,
    person_name: str | None = Query(
        default=None,
        description=(
            "Display name for the person, used to label the created layer. "
            "The person id remains the layer's sync key either way."
        ),
    ),
    db: Session = Depends(get_db),
    access_token: str = Depends(get_access_token),
    current_user=Depends(require_roles_for_case(CAN_WRITE)),
) -> FrsPersonHistoryImportResponse:
    """Import one person's sighting history as a GIS layer.

    FRS reports one entry per detection, so a person walking past a
    camera yields a long run of entries at the same coordinates. They
    are collapsed per camera into one point each, carrying how many
    sightings it represents and when they occurred, because a stack of
    near-identical pins would bury the places that actually matter.

    The write role is required because this route creates a layer and
    its features. `person_name` is optional and only labels the layer;
    an import without it still reconciles on the person id.
    """
    logger.info(
        "GET /cases/%s/face-recognition-system/persons/%s/history | user_id=%s | "
        "role=%s | person_name=%s",
        case_id,
        person_id,
        current_user["user_id"],
        current_user["role"],
        person_name,
    )

    return await import_person_history(
        case_id,
        person_id,
        access_token,
        db,
        person_name=person_name,
        created_by=current_user["user_id"],
    )


@router.get(
    "/cases/{case_id}/face-recognition-system/persons/{person_id}/route",
    response_model=FrsPersonRouteResponse,
    status_code=STATUS_OK,
    summary="Read one person's FRS sightings as an ordered route",
)
async def get_frs_person_route(
    case_id: int,
    person_id: int,
    limit: int = Query(
        default=500,
        ge=1,
        le=5000,
        description=(
            "Maximum sightings to return, oldest first. A long-running case "
            "can hold thousands of detections for one person, and the "
            "earliest ones are what a route view usually needs."
        ),
    ),
    db: Session = Depends(get_db),
    access_token: str = Depends(get_access_token),
    current_user=Depends(require_roles_for_case(CAN_WRITE)),
) -> FrsPersonRouteResponse:
    """Read one person's stored sightings in the order they happened.

    Read-only and entirely local: no provider call and nothing is written.
    The detections have to be in frs_person_sightings first, which the
    history import populates; the map layer cannot answer this, because it
    deliberately collapses per-detection entries into one point per camera.

    Every point is a detection AT a camera, not a measured position of the
    subject — the provider reports the camera's own coordinates, so a person
    passing ten metres past a lens is still reported at the lens. The caller
    draws the line; this route only supplies the ordered sequence, the
    per-point timestamps and the camera each came from.

    `single_video` reports how far that ordering can be trusted. Within one
    video the sequence is sound (one camera, one clock). Across videos it
    rests on the provider normalising every camera to UTC, which it asserts
    but exposes no way to verify, so a multi-camera route is an INFERRED
    sequence rather than a measured path.

    The write role is still required. Sightings are investigative evidence,
    the same gate as the import routes, and this data is no less sensitive
    than the layers it accompanies.
    """
    logger.info(
        "GET /cases/%s/face-recognition-system/persons/%s/route | user_id=%s | "
        "role=%s | limit=%s",
        case_id,
        person_id,
        current_user["user_id"],
        current_user["role"],
        limit,
    )

    return person_route(case_id, str(person_id), db, limit=limit)

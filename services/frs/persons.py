import json
from typing import Any

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from models.model import Feature, Layer
from schemas.frs_schema import (
    FrsPerson as FrsPersonPayload,
    FrsPersonHistoryEntry,
    FrsPersonHistoryImportResponse,
    FrsPersonHistoryPoint,
)
from services.feature.feature_service import create_features_batch
from services.frs.registry import (
    link_person_layer,
    upsert_persons,
    upsert_sightings,
)
from services.layer.layer_service import create_layer, get_layer
from utils.config import settings
from utils.constants import (
    FRS_INVALID_RESPONSE,
    FRS_LAYER_NAME_MAX_LENGTH,
    FRS_MODULE_SLUG,
    FRS_NO_PERSONS,
    FRS_NOT_CONFIGURED,
    FRS_PERSON_FEATURE_NAME_TEMPLATE,
    FRS_PERSON_HISTORY_PATH,
    FRS_PERSON_IMPORT_FAILED,
    FRS_PERSON_LAYER_NAME_TEMPLATE,
    FRS_PERSON_LAYER_NAME_TRUNCATED,
    FRS_PERSON_LAYER_TYPE,
    FRS_PERSON_NO_COORDINATES,
    FRS_PERSONS_PATH,
)
from utils.exceptions import ServiceUnavailableError
from utils.logger import logger

# The transport, broadcast, reconciliation and staleness helpers are the
# same ones the camera module uses, imported rather than copied: a
# divergent second copy of "did this feature change" or "commit before
# the request-scoped session closes" is exactly the kind of drift that
# makes two integrations disagree about what a re-import does.
from services.frs.cameras import (
    _broadcast_features,
    _broadcast_layer_created,
    _feature_needs_update,
    fetch_json,
)


def _base_url() -> str:
    
    base_url = (settings.FRS_API_BASE_URL or "").strip().rstrip("/")
    if not base_url:
        logger.error("FRS base URL is not configured")
        raise ServiceUnavailableError(FRS_NOT_CONFIGURED)
    return base_url


def build_persons_url(case_id: int) -> str:
    
    return f"{_base_url()}{FRS_PERSONS_PATH}?case_id={case_id}"


def build_person_history_url(case_id: int, person_id: int) -> str:
    """Build the case-scoped sighting history URL for one person."""
    path = FRS_PERSON_HISTORY_PATH.format(person_id=person_id)
    return f"{_base_url()}{path}?case_id={case_id}"


def layer_name_for_person(person_id: Any, person_name: str | None) -> str:
    
    prefix, _, _ = FRS_PERSON_LAYER_NAME_TEMPLATE.partition("{person_name}")
    suffix = f" ({person_id})"
    label = (person_name or "").strip()

    if not label:
        # No display name yet: render the id-only form rather than leaving
        # the placeholder's leading space behind as "FRS Person  (7)".
        name = f"FRS Person ({person_id})"
    else:
        name = FRS_PERSON_LAYER_NAME_TEMPLATE.format(
            person_name=label, person_id=person_id
        )
    if len(name) <= FRS_LAYER_NAME_MAX_LENGTH:
        return name

    # The prefix and the id suffix are both load-bearing, so the display
    # name is the only part that gives way, and it gives exactly enough
    # to fill the column.
    budget = FRS_LAYER_NAME_MAX_LENGTH - len(prefix) - len(suffix)
    truncated = f"{prefix}{label[:max(budget, 0)]}{suffix}"
    logger.warning(
        FRS_PERSON_LAYER_NAME_TRUNCATED + " | person_id=%s | name=%s",
        FRS_LAYER_NAME_MAX_LENGTH,
        person_id,
        truncated,
    )
    return truncated


def feature_name_for_point(point: FrsPersonHistoryPoint, person_id: Any) -> str:
    
    if point.camera_name:
        return f"{point.camera_name} ({person_id})"
    if point.camera_id is not None:
        return FRS_PERSON_FEATURE_NAME_TEMPLATE.format(
            person_id=person_id, camera_id=point.camera_id
        )
    return f"FRS Person {person_id} sighting"


def _unwrap(raw: Any, what: str, case_id: int) -> list[dict]:
    """Accept a bare array or a dict keyed by a list-bearing name."""
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]

    if isinstance(raw, dict):
        for key in ("data", "persons", "history", "results", "items"):
            candidate = raw.get(key)
            if isinstance(candidate, list):
                return [item for item in candidate if isinstance(item, dict)]

    observed = sorted(raw) if isinstance(raw, dict) else type(raw).__name__
    logger.warning(
        "FRS %s payload had no usable data list | case_id=%s | keys=%s",
        what,
        case_id,
        observed,
    )
    raise ServiceUnavailableError(FRS_INVALID_RESPONSE)


async def fetch_persons(
    case_id: int, access_token: str
) -> list[FrsPersonPayload]:
    
    url = build_persons_url(case_id)
    payload = await fetch_json(url, access_token)
    items = _unwrap(payload, "person", case_id)

    persons: list[FrsPersonPayload] = []
    invalid = 0
    for item in items:
        try:
            persons.append(FrsPersonPayload.model_validate(item))
        except ValidationError as exc:
            invalid += 1
            logger.warning("FRS person record skipped: invalid | error=%s", exc)

    if not persons:
        logger.info("FRS case has no persons | case_id=%s | %s", case_id, FRS_NO_PERSONS)

    logger.info(
        "FRS persons fetched | case_id=%s | persons=%s | invalid=%s",
        case_id,
        len(persons),
        invalid,
    )
    return persons


async def fetch_person_history(
    case_id: int, person_id: int, access_token: str
) -> list[FrsPersonHistoryEntry]:
    
    url = build_person_history_url(case_id, person_id)
    payload = await fetch_json(url, access_token)
    items = _unwrap(payload, "person history", case_id)

    entries: list[FrsPersonHistoryEntry] = []
    invalid = 0
    for item in items:
        try:
            entries.append(FrsPersonHistoryEntry.model_validate(item))
        except ValidationError as exc:
            invalid += 1
            logger.warning(
                "FRS person history entry skipped: invalid | person_id=%s | error=%s",
                person_id,
                exc,
            )

    logger.info(
        "FRS person history fetched | case_id=%s | person_id=%s | entries=%s | "
        "invalid=%s",
        case_id,
        person_id,
        len(entries),
        invalid,
    )
    return entries


def collapse_sightings(
    entries: list[FrsPersonHistoryEntry],
    person_id: Any = None,
    person_name: str | None = None,
) -> tuple[list[FrsPersonHistoryPoint], int]:
    
    groups: dict[str, list[FrsPersonHistoryEntry]] = {}
    skipped = 0

    for entry in entries:
        if not entry.has_usable_coordinates:
            skipped += 1
            continue
        groups.setdefault(entry.camera_key, []).append(entry)

    points: list[FrsPersonHistoryPoint] = []
    for group in groups.values():
        first = group[0]

        confidences = [item.confidence for item in group if item.confidence is not None]
        similarities = [item.similarity for item in group if item.similarity is not None]
        started = [item.started_at for item in group if item.started_at]
        ended = [item.ended_at for item in group if item.ended_at]
        videos = sorted({item.video_filename for item in group if item.video_filename})

        points.append(
            FrsPersonHistoryPoint(
                person_id=str(person_id) if person_id is not None else None,
                person_name=person_name,
                camera_id=first.camera_id,
                camera_name=next(
                    (item.camera_name for item in group if item.camera_name), None
                ),
                latitude=first.latitude,
                longitude=first.longitude,
                sighting_count=len(group),
                # Max, not first: a repeat detection of the same person
                # carries its own score, and the weakest one should not
                # define the sighting. Taking the first entry's value
                # would let an earlier, weaker detection hide a later,
                # stronger match.
                confidence=max(confidences) if confidences else None,
                similarity=max(similarities) if similarities else None,
                source=next((item.source for item in group if item.source), None),
                # min/max over the raw strings. The provider emits
                # ISO-8601 with a fixed UTC offset, which orders
                # lexicographically exactly as it orders
                # chronologically, so no parsing is needed — and not
                # parsing avoids rejecting an unrecognised format.
                first_seen=min(started) if started else None,
                last_seen=max(ended) if ended else None,
                videos=videos,
            )
        )

    return points, skipped


async def _get_or_create_person_layer(
    case_id: int, person_id: Any, person_name: str | None, db
) -> tuple[dict, bool]:
    """Return the person's sighting layer and whether it was created."""
    name = layer_name_for_person(person_id, person_name)

    try:
        existing_id = db.scalar(
            select(Layer.id)
            .where(
                Layer.case_id == case_id,
                Layer.name == name,
                Layer.module_slug == FRS_MODULE_SLUG,
            )
            .limit(1)
        )
    except SQLAlchemyError as exc:
        logger.error(
            "FRS person layer lookup failed | case_id=%s | person_id=%s | error=%s",
            case_id,
            person_id,
            exc,
            exc_info=True,
        )
        raise ServiceUnavailableError(FRS_PERSON_IMPORT_FAILED) from exc

    if existing_id is not None:
        return await get_layer(existing_id, db), False

    result = await create_layer(
        {
            "case_id": case_id,
            "name": name,
            "layer_type": FRS_PERSON_LAYER_TYPE,
            "module_slug": FRS_MODULE_SLUG,
            "visible": True,
        },
        db,
    )
    return await get_layer(result["layer_id"], db), True


def _existing_person_features(
    case_id: int, layer_id: int, db
) -> dict[str, tuple[Feature, Any]]:
    
    try:
        rows = db.execute(
            select(Feature, func.ST_AsGeoJSON(Feature.geom).label("geometry")).where(
                Feature.case_id == case_id,
                Feature.layer_id == layer_id,
                Feature.module_slug == FRS_MODULE_SLUG,
            )
        ).all()
    except SQLAlchemyError as exc:
        logger.error(
            "FRS person feature lookup failed | case_id=%s | layer_id=%s | error=%s",
            case_id,
            layer_id,
            exc,
            exc_info=True,
        )
        raise ServiceUnavailableError(FRS_PERSON_IMPORT_FAILED) from exc

    indexed: dict[str, tuple[Feature, Any]] = {}
    for feature, geometry in rows:
        properties = feature.properties
        if not isinstance(properties, dict):
            continue
        camera_id = properties.get("camera_id")
        latitude = properties.get("latitude")
        longitude = properties.get("longitude")
        key = (
            f"camera:{camera_id}"
            if camera_id is not None
            else f"point:{longitude},{latitude}"
        )
        indexed.setdefault(key, (feature, geometry))
    return indexed


def _stale_person_layer_count(
    case_id: int, person_id: Any, expected_name: str, db
) -> int:
    
    suffix = f" ({person_id})"

    try:
        return db.scalar(
            select(func.count())
            .select_from(Layer)
            .where(
                Layer.case_id == case_id,
                Layer.module_slug == FRS_MODULE_SLUG,
                Layer.name.endswith(suffix),
                Layer.name != expected_name,
            )
        ) or 0
    except SQLAlchemyError as exc:
        logger.error(
            "FRS stale person layer count failed | case_id=%s | person_id=%s | "
            "error=%s",
            case_id,
            person_id,
            exc,
            exc_info=True,
        )
        raise ServiceUnavailableError(FRS_PERSON_IMPORT_FAILED) from exc


async def _refresh_feature(
    feature: Feature, payload: dict, stored_geometry: Any, db
) -> bool:
    
    try:
        feature.name = payload["name"]
        feature.geometry_type = payload["geometry_type"]
        feature.properties = payload["properties"]
        feature.geom = func.ST_SetSRID(
            func.ST_GeomFromGeoJSON(json.dumps(payload["geometry"])), 4326
        )
        feature.updated_at = func.now()
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error(
            "FRS person feature refresh failed | feature_id=%s | error=%s",
            feature.id,
            exc,
            exc_info=True,
        )
        raise ServiceUnavailableError(FRS_PERSON_IMPORT_FAILED) from exc
    return True


def _point_payload(
    point: FrsPersonHistoryPoint, person_id: Any, layer_id: int
) -> dict:
    """Build the feature payload for one collapsed sighting point."""
    return {
        "name": feature_name_for_point(point, person_id),
        "geometry_type": "Point",
        "geometry": {
            "type": "Point",
            "coordinates": [point.longitude, point.latitude],
        },
        "module_slug": FRS_MODULE_SLUG,
        "properties": {
            "person_id": point.person_id,
            "person_name": point.person_name,
            "camera_id": point.camera_id,
            "camera_name": point.camera_name,
            "latitude": point.latitude,
            "longitude": point.longitude,
            "sighting_count": point.sighting_count,
            "confidence": point.confidence,
            "similarity": point.similarity,
            "source": point.source,
            "first_seen": point.first_seen,
            "last_seen": point.last_seen,
            "videos": point.videos,
        },
    }


async def import_person_history(
    case_id: int,
    person_id: int,
    access_token: str,
    db,
    person_name: str | None = None,
    created_by: int | None = None,
) -> FrsPersonHistoryImportResponse:
    
    entries = await fetch_person_history(case_id, person_id, access_token)

    if not entries:
        logger.info(
            "FRS person has no history, returning an empty import | "
            "case_id=%s | person_id=%s",
            case_id,
            person_id,
        )
        return FrsPersonHistoryImportResponse(
            case_id=case_id,
            person_id=person_id,
            person_name=person_name,
            entries=0,
            points=0,
            layers=[],
            layers_created=0,
            skipped_entries=0,
            sightings_created=0,
            sightings_updated=0,
            sightings_unordered=0,
        )

    person_key = str(person_id)

    # The person row is built from the history payload rather than from the
    # /persons listing, so pulling one person's history is enough to make
    # them exist. The route endpoint 404s when there is no row, and the
    # registry has to be there for the sightings to point at. Guarded before
    # the collapse, so a history with no mappable locations still records
    # that the person was seen at all.
    upsert_persons(
        case_id,
        [
            FrsPersonPayload.model_validate(
                {"id": person_key, "name": person_name}
            )
        ],
        db,
    )

    # Before the collapse, deliberately. collapse_sightings reduces the
    # detections to one point per camera, which is right for the map and is
    # exactly what destroys the ordering this table exists to keep.
    sightings_created, sightings_updated, sightings_unordered = upsert_sightings(
        case_id, person_key, entries, db
    )

    points, skipped = collapse_sightings(entries, person_id, person_name)

    if not points:
        logger.info(
            "FRS person history has no mappable locations, so no layer is "
            "created; returning the sighting import alone | case_id=%s | "
            "person_id=%s | entries=%s | skipped=%s",
            case_id,
            person_id,
            len(entries),
            skipped,
        )
        return FrsPersonHistoryImportResponse(
            case_id=case_id,
            person_id=person_id,
            person_name=person_name,
            message=FRS_PERSON_NO_COORDINATES,
            entries=len(entries),
            points=0,
            layers=[],
            layers_created=0,
            skipped_entries=skipped,
            sightings_created=sightings_created,
            sightings_updated=sightings_updated,
            sightings_unordered=sightings_unordered,
        )

    layer, layer_created = await _get_or_create_person_layer(
        case_id, person_id, person_name, db
    )
    layer_id = layer["id"]
    if layer_created:
        await _broadcast_layer_created(layer)

    # After the layer exists, since layer_id is what is being linked.
    link_person_layer(case_id, person_key, layer_id, db)

    existing = _existing_person_features(case_id, layer_id, db)

    pending: list[dict] = []
    refreshed: list[dict] = []
    features_unchanged = 0

    for point in points:
        payload = _point_payload(point, person_id, layer_id)
        match = existing.get(point.camera_key)

        if match is None:
            pending.append(payload)
            continue

        feature, stored_geometry = match
        if not _feature_needs_update(feature, payload, stored_geometry):
            features_unchanged += 1
            continue

        await _refresh_feature(feature, payload, stored_geometry, db)
        refreshed.append(
            {
                "id": feature.id,
                "layer_id": layer_id,
                "name": payload["name"],
                "geometry": payload["geometry"],
                "geometry_type": payload["geometry_type"],
                "properties": payload["properties"],
            }
        )

    features_created = 0
    if pending:
        # create_features_batch is synchronous; it is not awaited.
        created = create_features_batch(
            pending,
            case_id,
            layer_id,
            db,
            created_by=created_by,
            module_slug=FRS_MODULE_SLUG,
        )
        features_created = len(created)
        await _broadcast_features("feature.batch_created", case_id, layer_id, created)

    if refreshed:
        await _broadcast_features(
            "feature.batch_updated", case_id, layer_id, refreshed
        )

    layers_created = 1 if layer_created else 0
    layers_reused = 0 if layer_created else 1
    layers_stale = _stale_person_layer_count(case_id, person_id, layer["name"], db)

    logger.info(
        "FRS person history imported | case_id=%s | person_id=%s | entries=%s | "
        "points=%s | layers_created=%s | layers_reused=%s | layers_stale=%s | "
        "features_created=%s | features_updated=%s | features_unchanged=%s | "
        "skipped_entries=%s | sightings_created=%s | sightings_updated=%s | "
        "sightings_unordered=%s",
        case_id,
        person_id,
        len(entries),
        len(points),
        layers_created,
        layers_reused,
        layers_stale,
        features_created,
        len(refreshed),
        features_unchanged,
        skipped,
        sightings_created,
        sightings_updated,
        sightings_unordered,
    )

    return FrsPersonHistoryImportResponse(
        case_id=case_id,
        person_id=person_id,
        person_name=person_name,
        entries=len(entries),
        points=len(points),
        layers=[layer],
        layers_created=layers_created,
        skipped_entries=skipped,
        sightings_created=sightings_created,
        sightings_updated=sightings_updated,
        sightings_unordered=sightings_unordered,
    )

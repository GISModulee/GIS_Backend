from datetime import datetime, timezone
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from models.model import FrsCamera, FrsPerson, FrsPersonSighting
from schemas.frs_schema import (
    FrsCamera as FrsCameraPayload,
    FrsPerson as FrsPersonPayload,
    FrsPersonHistoryEntry,
    FrsPersonRouteResponse,
    FrsSightingPoint,
)
from utils.constants import (
    FRS_CAMERA_MOVED,
    FRS_NO_PERSON_HISTORY,
    FRS_REGISTRY_READ_FAILED,
    FRS_REGISTRY_WRITE_FAILED,
    FRS_ROUTE_FAILED,
    FRS_SIGHTING_UNORDERED_SKIPPED,
)
from utils.exceptions import NotFoundError, ServiceUnavailableError
from utils.logger import logger


# Two cameras reported at coordinates this far apart are treated as the
# same position. Below this, the difference is float noise in the
# provider's own serialisation rather than a real relocation.
_COORDINATE_EPSILON = 1e-6


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_timestamp(value: Any) -> datetime | None:
    
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.endswith(("Z", "z")):
            text = f"{text[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
    else:
        return None

    if parsed.tzinfo is None or parsed.tzinfo.utcoffset(parsed) is None:
        return None
    return parsed.astimezone(timezone.utc)


def _write_error(message: str, exc: Exception, **context: Any) -> ServiceUnavailableError:
    """Roll the session back, log the failure, and build the raised error.

    Shared by every write function so a registry failure always reads the
    same way in the log regardless of which import raised it.
    """
    db = context.pop("db", None)
    if db is not None:
        db.rollback()
    details = " | ".join(f"{key}={value}" for key, value in context.items())
    logger.error(
        f"{message} | {details} | error=%s" if details else f"{message} | error=%s",
        exc,
        exc_info=True,
    )
    return ServiceUnavailableError(FRS_REGISTRY_WRITE_FAILED)


def _positions_differ(
    a_lat: float | None,
    a_long: float | None,
    b_lat: float | None,
    b_long: float | None,
) -> bool:
    """Whether two coordinate pairs disagree by more than float noise."""
    for left, right in ((a_lat, b_lat), (a_long, b_long)):
        if left is None or right is None:
            if left is not right:
                return True
            continue
        if abs(left - right) > _COORDINATE_EPSILON:
            return True
    return False


def upsert_cameras(
    cameras: Iterable[FrsCameraPayload], db
) -> tuple[int, int, list[str]]:
    
    try:
        payloads = list(cameras)
        existing = {
            row.camera_id: row
            for row in db.scalars(select(FrsCamera)).all()
        }

        created = 0
        updated = 0
        moved: list[str] = []

        for camera in payloads:
            row = existing.get(camera.camera_id)

            if row is None:
                db.add(
                    FrsCamera(
                        camera_id=camera.camera_id,
                        name=camera.name,
                        zone=camera.zone,
                        status=camera.status,
                        latitude=camera.latitude,
                        longitude=camera.longitude,
                        frs_case_id=camera.frs_case_id,
                    )
                )
                created += 1
                continue

            if _positions_differ(
                row.latitude, row.longitude, camera.latitude, camera.longitude
            ):
                logger.info(
                    FRS_CAMERA_MOVED,
                    camera.camera_id,
                    row.latitude,
                    row.longitude,
                    camera.latitude,
                    camera.longitude,
                )
                row.coordinates_changed_at = _now()
                moved.append(camera.camera_id)

            row.name = camera.name
            row.zone = camera.zone
            row.status = camera.status
            row.latitude = camera.latitude
            row.longitude = camera.longitude
            row.frs_case_id = camera.frs_case_id
            updated += 1

        # Commits rather than flushes: get_db closes the request-scoped
        # session without committing, so a flush-only write would be rolled
        # back at the end of the request. See _refresh_feature in
        # cameras.py, which documents the same constraint.
        db.commit()
        return created, updated, moved
    except SQLAlchemyError as exc:
        raise _write_error(
            "FRS camera registry write failed", exc, db=db
        ) from exc


def list_cameras(db) -> list[FrsCamera]:
    
    try:
        return list(
            db.scalars(select(FrsCamera).order_by(FrsCamera.camera_id)).all()
        )
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error(
            "FRS camera registry read failed | error=%s", exc, exc_info=True
        )
        raise ServiceUnavailableError(FRS_REGISTRY_READ_FAILED) from exc


def upsert_persons(
    case_id: int, persons: Iterable[FrsPersonPayload], db
) -> tuple[int, int]:
    
    try:
        payloads = list(persons)
        created = 0
        updated = 0

        for person in payloads:
            row = db.get(
                FrsPerson, {"case_id": case_id, "person_id": person.person_id}
            )

            if row is None:
                db.add(
                    FrsPerson(
                        case_id=case_id,
                        person_id=person.person_id,
                        name=person.name,
                        organization=person.organization,
                        tags=person.tags,
                        provider_case_ids=person.case_ids,
                    )
                )
                created += 1
                continue

            if person.name is not None:
                row.name = person.name
            if person.organization is not None:
                row.organization = person.organization
            if person.tags:
                row.tags = person.tags
            if person.case_ids:
                row.provider_case_ids = person.case_ids
            updated += 1

        db.commit()
        return created, updated
    except SQLAlchemyError as exc:
        raise _write_error(
            "FRS person registry write failed", exc, case_id=case_id, db=db
        ) from exc


def link_person_layer(case_id: int, person_id: str, layer_id: int, db) -> None:
    
    try:
        row = db.get(FrsPerson, {"case_id": case_id, "person_id": person_id})

        if row is None:
            db.add(
                FrsPerson(
                    case_id=case_id,
                    person_id=person_id,
                    layer_id=layer_id,
                )
            )
        elif row.layer_id != layer_id:
            row.layer_id = layer_id

        db.commit()
    except SQLAlchemyError as exc:
        raise _write_error(
            "FRS person layer link failed",
            exc,
            case_id=case_id,
            person_id=person_id,
            layer_id=layer_id,
            db=db,
        ) from exc


def _register_missing_cameras(
    entries: list[FrsPersonHistoryEntry], db
) -> None:
    
    cited = {
        entry.camera_id: entry
        for entry in entries
        if entry.camera_id is not None
    }
    if not cited:
        return

    known = set(
        db.scalars(select(FrsCamera.camera_id).where(FrsCamera.camera_id.in_(cited))).all()
    )

    for camera_id, entry in cited.items():
        if camera_id in known:
            continue
        # Coordinates are only seeded when they are usable. The (0, 0)
        # sentinel is the provider's "no fix", and storing it would give
        # the row a registry position in the Gulf of Guinea, which the
        # camera_moved comparison would then treat as a known position to
        # agree or disagree with. No position is the honest state.
        usable = entry.has_usable_coordinates
        db.add(
            FrsCamera(
                camera_id=camera_id,
                name=entry.camera_name,
                latitude=entry.latitude if usable else None,
                longitude=entry.longitude if usable else None,
            )
        )
        logger.info(
            "FRS camera registered from a sighting | camera_id=%s | camera_name=%s",
            camera_id,
            entry.camera_name,
        )


def _camera_positions(
    entries: list[FrsPersonHistoryEntry], db
) -> dict[str, tuple[float | None, float | None]]:
    
    cited = {entry.camera_id for entry in entries if entry.camera_id is not None}
    if not cited:
        return {}

    rows = db.execute(
        select(FrsCamera.camera_id, FrsCamera.latitude, FrsCamera.longitude).where(
            FrsCamera.camera_id.in_(cited)
        )
    ).all()
    return {row[0]: (row[1], row[2]) for row in rows}


def upsert_sightings(
    case_id: int,
    person_id: str,
    entries: list[FrsPersonHistoryEntry],
    db,
) -> tuple[int, int, int]:
    
    try:
        usable: list[FrsPersonHistoryEntry] = []
        unordered = 0

        for entry in entries:
            if entry.has_timestamp and _parse_timestamp(entry.started_at):
                usable.append(entry)
                continue
            unordered += 1
            logger.info(
                FRS_SIGHTING_UNORDERED_SKIPPED, case_id, person_id
            )

        if not usable:
            return 0, 0, unordered

        # Cameras first, so a sighting citing an unknown one does not fail
        # the foreign key. Only flushed: the commit below owns the
        # transaction, and a commit here would persist a half-written
        # sighting set if the insert that follows failed.
        _register_missing_cameras(usable, db)
        db.flush()

        # Read AFTER the seed, so a camera first seen here is compared
        # against itself rather than reading as unknown-and-therefore-moved.
        positions = _camera_positions(usable, db)

        existing = {
            (row.video_id, row.camera_id, row.started_at): row
            for row in db.scalars(
                select(FrsPersonSighting).where(
                    FrsPersonSighting.case_id == case_id,
                    FrsPersonSighting.person_id == person_id,
                )
            ).all()
        }

        created = 0
        updated = 0

        for entry in usable:
            started_at = _parse_timestamp(entry.started_at)
            ended_at = _parse_timestamp(entry.ended_at)
            key = (entry.video_id, entry.camera_id, started_at)
            row = existing.get(key)

            registry_lat, registry_long = positions.get(entry.camera_id, (None, None))
            # A camera absent from the registry — or seeded from a sighting
            # with no usable fix, so its row has NULL coordinates — yields
            # no position here. That must read as "no known position", NOT
            # as "position matches" and not as "position disagrees": there
            # is nothing to compare against, and flagging it would report a
            # camera move that never happened.
            camera_moved = (
                registry_lat is not None
                and registry_long is not None
                and entry.latitude is not None
                and entry.longitude is not None
                and _positions_differ(
                    registry_lat,
                    registry_long,
                    entry.latitude,
                    entry.longitude,
                )
            )

            if row is None:
                db.add(
                    FrsPersonSighting(
                        case_id=case_id,
                        person_id=person_id,
                        video_id=entry.video_id,
                        started_at=started_at,
                        camera_id=entry.camera_id,
                        camera_name=entry.camera_name,
                        latitude=entry.latitude,
                        longitude=entry.longitude,
                        ended_at=ended_at,
                        confidence=entry.confidence,
                        similarity=entry.similarity,
                        source=entry.source,
                        video_filename=entry.video_filename,
                        camera_moved=camera_moved,
                    )
                )
                created += 1
                continue

            row.camera_id = entry.camera_id
            row.camera_name = entry.camera_name
            row.latitude = entry.latitude
            row.longitude = entry.longitude
            row.ended_at = ended_at
            row.confidence = entry.confidence
            row.similarity = entry.similarity
            row.source = entry.source
            row.video_filename = entry.video_filename
            row.camera_moved = camera_moved
            updated += 1

        db.commit()
        return created, updated, unordered
    except SQLAlchemyError as exc:
        raise _write_error(
            "FRS sighting registry write failed",
            exc,
            case_id=case_id,
            person_id=person_id,
            db=db,
        ) from exc


def list_route(
    case_id: int, person_id: str, db, limit: int | None = None
) -> list[FrsPersonSighting]:
    
    try:
        statement = (
            select(FrsPersonSighting)
            .where(
                FrsPersonSighting.case_id == case_id,
                FrsPersonSighting.person_id == person_id,
            )
            .order_by(
                FrsPersonSighting.started_at.asc(),
                FrsPersonSighting.video_id.asc(),
            )
        )
        if limit is not None:
            statement = statement.limit(limit)
        return list(db.scalars(statement).all())
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error(
            "FRS route read failed | case_id=%s | person_id=%s | error=%s",
            case_id,
            person_id,
            exc,
            exc_info=True,
        )
        raise ServiceUnavailableError(FRS_ROUTE_FAILED) from exc


def person_route(
    case_id: int, person_id: str, db, limit: int | None = None
) -> FrsPersonRouteResponse:
    
    try:
        person = db.get(FrsPerson, {"case_id": case_id, "person_id": person_id})
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error(
            "FRS person lookup failed | case_id=%s | person_id=%s | error=%s",
            case_id,
            person_id,
            exc,
            exc_info=True,
        )
        raise ServiceUnavailableError(FRS_ROUTE_FAILED) from exc

    if person is None:
        logger.info(
            "FRS route requested for a person that was never imported | "
            "case_id=%s | person_id=%s",
            case_id,
            person_id,
        )
        raise NotFoundError(FRS_NO_PERSON_HISTORY)

    sightings = list_route(case_id, person_id, db, limit=limit)

    camera_ids: list[str] = []
    for sighting in sightings:
        if sighting.camera_id is not None and sighting.camera_id not in camera_ids:
            camera_ids.append(sighting.camera_id)

    return FrsPersonRouteResponse(
        case_id=case_id,
        person_id=person_id,
        person_name=person.name,
        single_video=len({row.video_id for row in sightings}) <= 1,
        camera_ids=camera_ids,
        sightings=[
            FrsSightingPoint(
                sequence=index,
                person_id=row.person_id,
                video_id=row.video_id,
                started_at=row.started_at,
                ended_at=row.ended_at,
                camera_id=row.camera_id,
                camera_name=row.camera_name,
                latitude=row.latitude,
                longitude=row.longitude,
                confidence=row.confidence,
                similarity=row.similarity,
                source=row.source,
                video_filename=row.video_filename,
                camera_moved=row.camera_moved,
            )
            for index, row in enumerate(sightings)
        ],
        sightings_count=len(sightings),
        moved_camera_sightings=sum(1 for row in sightings if row.camera_moved),
    )
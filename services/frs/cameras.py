import json
from typing import Any, NamedTuple

import httpx
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from models.model import Feature, Layer
from schemas.frs_schema import (
    FrsCamera,
    FrsCameraRegistryResponse,
    FrsCameraRegistryRow,
    FrsCamerasPayload,
)
from services.feature.feature_service import create_features_batch
from services.feature.feature_websocket_manager import feature_connection_manager
from services.frs.registry import list_cameras, upsert_cameras
from services.layer.layer_service import create_layer, get_layer
from services.layer.layer_websocket_manager import layer_connection_manager
from utils.config import settings
from utils.constants import (
    FRS_CAMERAS_PATH,
    FRS_FEATURE_NAME_TEMPLATE,
    FRS_IMPORT_FAILED,
    FRS_INVALID_RESPONSE,
    FRS_LAYER_NAME_MAX_LENGTH,
    FRS_LAYER_NAME_TEMPLATE,
    FRS_LAYER_NAME_TRUNCATED,
    FRS_LAYER_TYPE,
    FRS_MODULE_SLUG,
    FRS_NO_CAMERAS,
    FRS_NOT_CONFIGURED,
    FRS_RATE_LIMITED,
    FRS_TIMEOUT,
    FRS_UNAUTHORIZED,
    FRS_UNAVAILABLE,
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


def _provider_error(status_code: int) -> AppException:
    
    if status_code in (STATUS_UNAUTHORIZED, STATUS_FORBIDDEN):
        return UnauthorizedError(FRS_UNAUTHORIZED)
    if status_code == STATUS_NOT_FOUND:
        return NotFoundError(FRS_INVALID_RESPONSE)
    return ServiceUnavailableError(
        FRS_RATE_LIMITED
        if status_code == STATUS_TOO_MANY_REQUESTS
        else FRS_UNAVAILABLE
    )


async def fetch_json(url: str, access_token: str) -> object:
    
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(settings.FRS_TIMEOUT_SECONDS)
        ) as client:
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {access_token}"},
            )
    except httpx.TimeoutException as exc:
        logger.warning("FRS request timed out | url=%s | error=%s", url, exc)
        raise GatewayTimeoutError(FRS_TIMEOUT) from exc
    except httpx.RequestError as exc:
        logger.warning(
            "FRS request failed | url=%s | error=%s", url, type(exc).__name__
        )
        raise ServiceUnavailableError(FRS_UNAVAILABLE) from exc

    if response.status_code != 200:
        logger.warning(
            "FRS returned an error | url=%s | status=%s", url, response.status_code
        )
        raise _provider_error(response.status_code)

    try:
        return response.json()
    except ValueError as exc:
        logger.warning("FRS returned malformed JSON | url=%s", url)
        raise ServiceUnavailableError(FRS_INVALID_RESPONSE) from exc


def build_cameras_url() -> str:
    
    base_url = (settings.FRS_API_BASE_URL or "").strip().rstrip("/")
    if not base_url:
        logger.error("FRS base URL is not configured")
        raise ServiceUnavailableError(FRS_NOT_CONFIGURED)
    return f"{base_url}{FRS_CAMERAS_PATH}"


async def fetch_cameras(access_token: str) -> list[Any]:
    
    url = build_cameras_url()
    payload = await fetch_json(url, access_token)

    try:
        return FrsCamerasPayload.model_validate(payload).data
    except ValidationError as exc:
        logger.warning(
            "FRS camera payload had no usable list | url=%s | error=%s", url, exc
        )
        raise ServiceUnavailableError(FRS_INVALID_RESPONSE) from exc


def layer_name_for_camera(camera_id: str) -> str:
    
    name = FRS_LAYER_NAME_TEMPLATE.format(camera_id=camera_id)
    if len(name) <= FRS_LAYER_NAME_MAX_LENGTH:
        return name

    prefix = FRS_LAYER_NAME_TEMPLATE.format(camera_id="")
    budget = FRS_LAYER_NAME_MAX_LENGTH - len(prefix)
    truncated = f"{prefix}{camera_id[:budget]}"
    logger.warning(
        FRS_LAYER_NAME_TRUNCATED + " | camera_id=%s | name=%s",
        FRS_LAYER_NAME_MAX_LENGTH,
        camera_id,
        truncated,
    )
    return truncated


def _parse_cameras(raw: list[Any]) -> tuple[list[FrsCamera], int]:
    
    cameras: list[FrsCamera] = []
    skipped = 0

    for item in raw:
        if not isinstance(item, dict):
            skipped += 1
            continue
        try:
            cameras.append(FrsCamera.model_validate(item))
        except ValidationError as exc:
            skipped += 1
            logger.warning(
                "FRS camera record skipped: invalid | error=%s", exc
            )

    if skipped:
        logger.warning(
            "FRS camera records skipped | skipped=%s | accepted=%s",
            skipped,
            len(cameras),
        )
    return cameras, skipped


class CameraRegistrySync(NamedTuple):
    

    cameras: list[FrsCamera]
    invalid: int
    created: int
    updated: int
    moved: list[str]


async def sync_camera_registry(access_token: str, db) -> CameraRegistrySync:
    
    raw = await fetch_cameras(access_token)
    cameras, invalid = _parse_cameras(raw)

    # Only cameras with a usable position are persisted. One without has no
    # coordinates for a sighting to point at, so storing it would create a
    # row nothing can usefully join to.
    created, updated, moved = upsert_cameras(
        (c for c in cameras if c.has_usable_coordinates), db
    )
    return CameraRegistrySync(cameras, invalid, created, updated, moved)


async def read_camera_registry(
    access_token: str,
    db,
    case_id: int | None = None,
    created_by: int | None = None,
) -> FrsCameraRegistryResponse:
    
    sync = await sync_camera_registry(access_token, db)

    # malformed records plus records that validated but have no usable
    # fix: neither is storable, and both are what the caller cannot plot.
    skipped = sync.invalid + sum(
        1 for camera in sync.cameras if not camera.has_usable_coordinates
    )
    rows = list_cameras(db)

    imported = None
    if case_id is not None:
        imported = await import_camera_layers(
            case_id, sync, db, created_by=created_by
        )

    logger.info(
        "FRS camera registry synced | case_id=%s | reported=%s | stored=%s | "
        "skipped_cameras=%s | registry_created=%s | registry_updated=%s | "
        "cameras_moved=%s | layers_created=%s | features_created=%s",
        case_id,
        len(sync.cameras),
        len(rows),
        skipped,
        sync.created,
        sync.updated,
        len(sync.moved),
        imported.layers_created if imported else 0,
        imported.features_created if imported else 0,
    )

    return FrsCameraRegistryResponse(
        data=[FrsCameraRegistryRow.model_validate(row) for row in rows],
        case_id=case_id,
        cameras=len(sync.cameras),
        registry_created=sync.created,
        registry_updated=sync.updated,
        cameras_moved=len(sync.moved),
        skipped_cameras=skipped,
        layers=imported.layers if imported else [],
        layers_created=imported.layers_created if imported else 0,
        layers_reused=imported.layers_reused if imported else 0,
        layers_stale=imported.layers_stale if imported else 0,
        features_created=imported.features_created if imported else 0,
        features_updated=imported.features_updated if imported else 0,
        features_unchanged=imported.features_unchanged if imported else 0,
    )


def _feature_payload(camera: FrsCamera) -> dict:

    return {
        "name": FRS_FEATURE_NAME_TEMPLATE.format(camera_id=camera.camera_id),
        "geometry_type": "Point",
        "geometry": {
            "type": "Point",
            "coordinates": [camera.longitude, camera.latitude],
        },
        "module_slug": FRS_MODULE_SLUG,
        "properties": {
            "camera_id": camera.camera_id,
            "camera_name": camera.name,
            "zone": camera.zone,
            "status": camera.status,
            "frs_case_id": camera.frs_case_id,
            "latitude": camera.latitude,
            "longitude": camera.longitude,
        },
    }


async def _get_or_create_camera_layer(
    case_id: int, camera_id: str, db
) -> tuple[dict, bool]:
    
    name = layer_name_for_camera(camera_id)

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
            "FRS camera layer lookup failed | case_id=%s | camera_id=%s | error=%s",
            case_id,
            camera_id,
            exc,
            exc_info=True,
        )
        raise ServiceUnavailableError(FRS_IMPORT_FAILED) from exc

    if existing_id is not None:
        return await get_layer(existing_id, db), False

    result = await create_layer(
        {
            "case_id": case_id,
            "name": name,
            "layer_type": FRS_LAYER_TYPE,
            "module_slug": FRS_MODULE_SLUG,
            "visible": True,
        },
        db,
    )
    return await get_layer(result["layer_id"], db), True


def _existing_camera_feature(
    case_id: int, layer_id: int, camera_id: str, db
) -> tuple[Feature, dict] | None:
    
    try:
        row = db.execute(
            select(Feature, func.ST_AsGeoJSON(Feature.geom).label("geometry"))
            .where(
                Feature.case_id == case_id,
                Feature.layer_id == layer_id,
                Feature.module_slug == FRS_MODULE_SLUG,
                Feature.properties["camera_id"].as_string() == camera_id,
            )
            .limit(1)
        ).first()
    except SQLAlchemyError as exc:
        logger.error(
            "FRS camera feature lookup failed | case_id=%s | layer_id=%s | "
            "camera_id=%s | error=%s",
            case_id,
            layer_id,
            camera_id,
            exc,
            exc_info=True,
        )
        raise ServiceUnavailableError(FRS_IMPORT_FAILED) from exc

    if row is None:
        return None
    return row[0], row[1]


def _coordinates_match(stored_geometry: Any, incoming: dict) -> bool:
    
    if not isinstance(stored_geometry, str):
        return False
    try:
        parsed = json.loads(stored_geometry)
    except (TypeError, ValueError):
        return False

    if not isinstance(parsed, dict):
        return False
    stored_coordinates = parsed.get("coordinates")
    return stored_coordinates == incoming.get("coordinates")


def _feature_needs_update(feature: Feature, payload: dict, stored_geometry: Any) -> bool:
    if feature.name != payload["name"]:
        return True
    if feature.geometry_type != payload["geometry_type"]:
        return True
    if feature.properties != payload["properties"]:
        return True
    return not _coordinates_match(stored_geometry, payload["geometry"])


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
            "FRS camera feature refresh failed | feature_id=%s | error=%s",
            feature.id,
            exc,
            exc_info=True,
        )
        raise ServiceUnavailableError(FRS_IMPORT_FAILED) from exc
    return True


async def _broadcast_layer_created(layer: dict) -> None:
    message = {
        "event": "layer.created",
        "case_id": layer["case_id"],
        "layer": layer,
    }
    await layer_connection_manager.broadcast(layer["case_id"], message)
    await feature_connection_manager.broadcast(layer["case_id"], message)


async def _broadcast_features(
    event: str, case_id: int, layer_id: int, features: list[dict]
) -> None:
    if not features:
        return
    await feature_connection_manager.broadcast(
        case_id,
        {
            "event": event,
            "case_id": case_id,
            "layer_id": layer_id,
            "count": len(features),
            "features": features,
        },
    )


def _stale_layer_count(case_id: int, expected_names: set[str], db) -> int:
    
    try:
        return db.scalar(
            select(func.count())
            .select_from(Layer)
            .where(
                Layer.case_id == case_id,
                Layer.module_slug == FRS_MODULE_SLUG,
                Layer.layer_type == FRS_LAYER_TYPE,
                Layer.name.not_in(expected_names),
            )
        ) or 0
    except SQLAlchemyError as exc:
        logger.error(
            "FRS stale camera layer count failed | case_id=%s | error=%s",
            case_id,
            exc,
            exc_info=True,
        )
        raise ServiceUnavailableError(FRS_IMPORT_FAILED) from exc


class CameraLayerImport(NamedTuple):
    

    layers: list[dict]
    layers_created: int
    layers_reused: int
    layers_stale: int
    features_created: int
    features_updated: int
    features_unchanged: int


async def import_camera_layers(
    case_id: int,
    sync: CameraRegistrySync,
    db,
    created_by: int | None = None,
) -> CameraLayerImport:
    
    cameras = sync.cameras

    if not cameras:
        logger.info(
            "FRS registry reported no cameras | case_id=%s | %s", case_id, FRS_NO_CAMERAS
        )

    layers: list[dict] = []
    layers_created = 0
    features_created = 0
    features_updated = 0
    features_unchanged = 0
    skipped_cameras = sync.invalid
    expected_names: set[str] = set()

    for camera in cameras:
        if not camera.has_usable_coordinates:
            skipped_cameras += 1
            logger.info(
                "FRS camera skipped: no usable fix | case_id=%s | camera_id=%s",
                case_id,
                camera.camera_id,
            )
            continue

        layer, layer_created = await _get_or_create_camera_layer(
            case_id, camera.camera_id, db
        )
        layer_id = layer["id"]
        layers.append(layer)
        expected_names.add(layer["name"])
        if layer_created:
            layers_created += 1
            await _broadcast_layer_created(layer)

        payload = _feature_payload(camera)
        existing = _existing_camera_feature(case_id, layer_id, camera.camera_id, db)

        if existing is None:
            # create_features_batch is synchronous; it is not awaited.
            created = create_features_batch(
                [payload],
                case_id,
                layer_id,
                db,
                created_by=created_by,
                module_slug=FRS_MODULE_SLUG,
            )
            features_created += len(created)
            await _broadcast_features(
                "feature.batch_created", case_id, layer_id, created
            )
            continue

        feature, stored_geometry = existing
        if not _feature_needs_update(feature, payload, stored_geometry):
            features_unchanged += 1
            continue

        await _refresh_feature(feature, payload, stored_geometry, db)
        features_updated += 1
        await _broadcast_features(
            "feature.batch_updated",
            case_id,
            layer_id,
            [
                {
                    "id": feature.id,
                    "layer_id": layer_id,
                    "name": payload["name"],
                    "geometry": payload["geometry"],
                    "geometry_type": payload["geometry_type"],
                    "properties": payload["properties"],
                }
            ],
        )

    layers_reused = len(layers) - layers_created
    layers_stale = _stale_layer_count(case_id, expected_names, db)

    logger.info(
        "FRS cameras imported | case_id=%s | reported=%s | layers_created=%s | "
        "layers_reused=%s | layers_stale=%s | features_created=%s | "
        "features_updated=%s | features_unchanged=%s | skipped_cameras=%s | "
        "registry_created=%s | registry_updated=%s | cameras_moved=%s",
        case_id,
        len(cameras),
        layers_created,
        layers_reused,
        layers_stale,
        features_created,
        features_updated,
        features_unchanged,
        skipped_cameras,
        sync.created,
        sync.updated,
        len(sync.moved),
    )

    return CameraLayerImport(
        layers=layers,
        layers_created=layers_created,
        layers_reused=layers_reused,
        layers_stale=layers_stale,
        features_created=features_created,
        features_updated=features_updated,
        features_unchanged=features_unchanged,
    )

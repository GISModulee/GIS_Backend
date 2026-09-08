from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from database.database import get_db
from utils.constants import FEATURE_NOT_FOUND, LAYER_NOT_FOUND, WEBSOCKET_AUTH_REQUIRED, WEBSOCKET_POLICY_VIOLATION
from utils.logger import logger
from utils.exceptions import NotFoundError
from utils.dependencies import authorize_case, enforce_role, get_access_token, get_current_user, get_current_case_context, require_roles, require_roles_for_case
from utils.roles import CAN_WRITE, CAN_DELETE_OPERATIONAL
from schemas.feature_schema import (
    FeatureActionResponse,
    FeatureCreate,
    FeatureCreateResponse,
    MeasurementFeatureCreate,
    FeaturePatch,
    FeatureResponse,
    FeatureSummaryResponse,
)

from services.feature.feature_service import (
    create_feature,
    get_features,
    get_feature,
    get_feature_by_number,
    get_layer_features,
    get_case_features,
    update_feature,
    delete_feature,
    patch_feature,
    save_measurement_feature,
)
from services.feature.feature_websocket_manager import feature_connection_manager
from services.layer.layer_service import get_layer
from services.layer.layer_websocket_manager import layer_connection_manager

router = APIRouter(tags=["Features"])


# ===================================================
# CREATE FEATURE — Investigator, Department Lead, Case Lead
# NOTE: case_id is inside the request body (feature.case_id), not a
# path param, so this stays token-only for now, same reasoning as
# POST /cases and POST /layers.
# ===================================================
@router.post("/features", response_model=FeatureCreateResponse)
async def add_feature(
    feature: FeatureCreate,
    db: Session = Depends(get_db),
    access_token: str = Depends(get_access_token),
):
    current_user = enforce_role(await authorize_case(access_token, feature.case_id), CAN_WRITE)
    logger.info(
        f"POST /features | user_id={current_user['user_id']} "
        f"| role={current_user['role']} "
        f"| body={feature.model_dump()}"
    )

    requested_layer_id = feature.layer_id

    result = await create_feature(
        feature,
        db,
        current_user["user_id"]
    )

    created_feature = await get_feature(
        result["feature_id"],
        db
    )

    await feature_connection_manager.broadcast(
        result["case_id"],
        {
            "event": "feature.created",
            "case_id": result["case_id"],
            "layer_id": result["layer_id"],
            "feature": created_feature,
        },
    )

    if requested_layer_id is None:
        created_layer = await get_layer(result["layer_id"], db)
        layer_message = {
            "event": "layer.created",
            "case_id": result["case_id"],
            "layer": created_layer,
        }
        await layer_connection_manager.broadcast(
            result["case_id"],
            layer_message,
        )

    return result


@router.post(
    "/cases/{case_id}/layers/{layer_id}/features/measurement",
    response_model=FeatureResponse,
)
async def add_measurement_feature(
    case_id: int,
    layer_id: int,
    measurement: MeasurementFeatureCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles_for_case(CAN_WRITE)),
):
    created_feature = await save_measurement_feature(
        db=db,
        case_id=case_id,
        layer_id=layer_id,
        geometry=measurement.geometry,
        measurement_type=measurement.measurement_type,
        distance_meters=measurement.distance_meters,
        user_id=current_user["user_id"],
    )

    await feature_connection_manager.broadcast(
        case_id,
        {
            "event": "feature.created",
            "case_id": case_id,
            "layer_id": layer_id,
            "feature": created_feature,
        },
    )

    return created_feature

# ===================================================
# UPDATE FEATURE (FULL) — Investigator, Department Lead, Case Lead
# ===================================================
@router.put("/cases/{case_id}/layers/{layer_id}/features/{feature_id}", response_model=FeatureActionResponse)
async def edit_feature(
    case_id: int,
    layer_id: int,
    feature_id: int,
    feature: FeatureCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles_for_case(CAN_WRITE))
):

    logger.info(f"PUT /cases/{case_id}/layers/{layer_id}/features/{feature_id} | user_id={current_user['user_id']} | role={current_user['role']}")

    existing = await get_feature(feature_id, db)

    if existing is None or existing["layer_id"] != layer_id or existing["case_id"] != case_id:
        logger.warning(f"Feature not found | case_id={case_id} | layer_id={layer_id} | feature_id={feature_id}")
        raise NotFoundError(FEATURE_NOT_FOUND)

    feature.case_id = case_id
    feature.layer_id = layer_id

    result = await update_feature(feature_id, feature, db)

    updated_feature = await get_feature(feature_id, db)

    await feature_connection_manager.broadcast(
        case_id,
        {
            "event": "feature.updated",
            "case_id": case_id,
            "layer_id": layer_id,
            "feature": updated_feature,
        },
    )

    return result


# ===================================================
# PATCH FEATURE (PARTIAL) — Investigator, Department Lead, Case Lead
# ===================================================
@router.patch("/cases/{case_id}/layers/{layer_id}/features/{feature_id}", response_model=FeatureActionResponse)
async def edit_feature_partial(
    case_id: int,
    layer_id: int,
    feature_id: int,
    feature: FeaturePatch,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles_for_case(CAN_WRITE))
):

    logger.info(f"PATCH /cases/{case_id}/layers/{layer_id}/features/{feature_id} | user_id={current_user['user_id']} | role={current_user['role']}")

    existing = await get_feature(feature_id, db)

    if existing is None or existing["layer_id"] != layer_id or existing["case_id"] != case_id:
        logger.warning(f"Feature not found | case_id={case_id} | layer_id={layer_id} | feature_id={feature_id}")
        raise NotFoundError(FEATURE_NOT_FOUND)

    result = await patch_feature(feature_id, feature, db)

    updated_feature = await get_feature(feature_id, db)

    await feature_connection_manager.broadcast(
        case_id,
        {
            "event": "feature.updated",
            "case_id": case_id,
            "layer_id": layer_id,
            "feature": updated_feature,
        },
    )

    return result


# ===================================================
# DELETE FEATURE — Investigator, Department Lead, Case Lead
# ===================================================
@router.delete("/cases/{case_id}/layers/{layer_id}/features/{feature_id}", response_model=FeatureActionResponse)
async def remove_feature(
    case_id: int,
    layer_id: int,
    feature_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles_for_case(CAN_DELETE_OPERATIONAL))
):

    logger.warning(f"DELETE /cases/{case_id}/layers/{layer_id}/features/{feature_id} | user_id={current_user['user_id']} | role={current_user['role']}")

    existing = await get_feature(feature_id, db)

    if existing is None or existing["layer_id"] != layer_id or existing["case_id"] != case_id:
        logger.warning(f"Feature not found | case_id={case_id} | layer_id={layer_id} | feature_id={feature_id}")
        raise NotFoundError(FEATURE_NOT_FOUND)

    result = await delete_feature(feature_id, db)

    await feature_connection_manager.broadcast(
        case_id,
        {
            "event": "feature.deleted",
            "case_id": case_id,
            "layer_id": layer_id,
            "feature_id": feature_id,
            "feature_number": existing["feature_number"],
        },
    )

    return result
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database.database import get_db

from schemas.vector_schema import (
    BufferOperation,
    CentroidOperation,
    ConvexHullOperation,
    VectorOperation
)

from services.vector.vector_services import (
    convex_hull,
    union_features,
    intersection_features,
    difference_features,
    symdifference_features,
    buffer_feature,
    centroid_feature
)
from services.feature.feature_service import get_feature
from services.layer.layer_service import get_layer
from services.layer.layer_websocket_manager import layer_connection_manager
from services.feature.feature_websocket_manager import feature_connection_manager

from utils.dependencies import get_current_user

router = APIRouter(
    prefix="/vector",
    tags=["Vector Operations"],
    dependencies=[Depends(get_current_user)]
)


async def _broadcast_vector_result_created(result, db):
    if not result:
        return

    layer_id = result.get("layer_id")
    feature_id = result.get("feature_id")
    if layer_id is None or feature_id is None:
        return

    created_layer = await get_layer(layer_id, db)
    if created_layer is None:
        return

    message = {
        "event": "layer.created",
        "case_id": created_layer["case_id"],
        "layer": created_layer,
    }
    await layer_connection_manager.broadcast(
        created_layer["case_id"],
        message,
    )
    await feature_connection_manager.broadcast(
        created_layer["case_id"],
        message,
    )

    created_feature = await get_feature(feature_id, db)
    if created_feature is None:
        return

    await feature_connection_manager.broadcast(
        created_layer["case_id"],
        {
            "event": "feature.created",
            "case_id": created_layer["case_id"],
            "layer_id": layer_id,
            "feature": created_feature,
        },
    )


@router.post("/union")
async def union(
    operation: VectorOperation,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await union_features(
        operation.case_id,
        operation.feature_numbers,
        db,
        current_user["user_id"],
        operation.layer_name,
    )
    await _broadcast_vector_result_created(result, db)
    return result


@router.post("/intersection")
async def intersection(
    operation: VectorOperation,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await intersection_features(
        operation.case_id,
        operation.feature_numbers,
        db,
        current_user["user_id"],
        operation.layer_name,
    )
    await _broadcast_vector_result_created(result, db)
    return result


@router.post("/difference")
async def difference(
    operation: VectorOperation,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await difference_features(
        operation.case_id,
        operation.feature_numbers,
        db,
        current_user["user_id"],
        operation.layer_name,
    )
    await _broadcast_vector_result_created(result, db)
    return result


@router.post("/symdifference")
async def symdifference(
    operation: VectorOperation,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await symdifference_features(
        operation.case_id,
        operation.feature_numbers,
        db,
        current_user["user_id"],
        operation.layer_name,
    )
    await _broadcast_vector_result_created(result, db)
    return result


@router.post("/buffer")
async def buffer(
    operation: BufferOperation,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await buffer_feature(
        operation.case_id,
        operation.feature_number,
        operation.distance,
        db,
        current_user["user_id"],
        operation.layer_name,
    )
    await _broadcast_vector_result_created(result, db)
    return result


@router.post("/centroid")
async def centroid(
    operation: CentroidOperation,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await centroid_feature(
        operation.case_id,
        operation.feature_number,
        db,
        current_user["user_id"],
        operation.layer_name,
    )
    await _broadcast_vector_result_created(result, db)
    return result


@router.post("/convex-hull")
async def convex(
    operation: ConvexHullOperation,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await convex_hull(
        operation.case_id,
        operation.feature_numbers,
        db,
        current_user["user_id"],
        operation.layer_name,
    )
    await _broadcast_vector_result_created(result, db)
    return result

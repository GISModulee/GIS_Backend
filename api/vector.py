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

from utils.dependencies import get_current_user

router = APIRouter(
    prefix="/vector",
    tags=["Vector Operations"],
    dependencies=[Depends(get_current_user)]
)


@router.post("/union")
async def union(
    operation: VectorOperation,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await union_features(
        operation.case_id,
        operation.feature_numbers,
        db,
        current_user["user_id"],
        operation.layer_name,
    )


@router.post("/intersection")
async def intersection(
    operation: VectorOperation,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await intersection_features(
        operation.case_id,
        operation.feature_numbers,
        db,
        current_user["user_id"],
        operation.layer_name,
    )


@router.post("/difference")
async def difference(
    operation: VectorOperation,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await difference_features(
        operation.case_id,
        operation.feature_numbers,
        db,
        current_user["user_id"],
        operation.layer_name,
    )


@router.post("/symdifference")
async def symdifference(
    operation: VectorOperation,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await symdifference_features(
        operation.case_id,
        operation.feature_numbers,
        db,
        current_user["user_id"],
        operation.layer_name,
    )


@router.post("/buffer")
async def buffer(
    operation: BufferOperation,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await buffer_feature(
        operation.case_id,
        operation.feature_number,
        operation.distance,
        db,
        current_user["user_id"],
        operation.layer_name,
    )


@router.post("/centroid")
async def centroid(
    operation: CentroidOperation,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await centroid_feature(
        operation.case_id,
        operation.feature_number,
        db,
        current_user["user_id"],
        operation.layer_name,
    )


@router.post("/convex-hull")
async def convex(
    operation: ConvexHullOperation,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await convex_hull(
        operation.case_id,
        operation.feature_numbers,
        db,
        current_user["user_id"],
        operation.layer_name,
    )

from fastapi import APIRouter, Depends

from schemas.vector_schema import (
    BufferOperation,
    CentroidOperation,
    ConvexHullOperation,
    VectorOperation
)

from services.vector_services import (
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
def union(operation: VectorOperation):
    return union_features(operation.feature_numbers)


@router.post("/intersection")
def intersection(operation: VectorOperation):
    return intersection_features(operation.feature_numbers)


@router.post("/difference")
def difference(operation: VectorOperation):
    return difference_features(operation.feature_numbers)


@router.post("/symdifference")
def symdifference(operation: VectorOperation):
    return symdifference_features(operation.feature_numbers)


@router.post("/buffer")
def buffer(operation: BufferOperation):
    return buffer_feature(
        operation.feature_number,
        operation.distance
    )


@router.post("/centroid")
def centroid(operation: CentroidOperation):
    return centroid_feature(operation.feature_number)


@router.post("/convex-hull")
def convex(operation: ConvexHullOperation):
    return convex_hull(operation.feature_numbers)
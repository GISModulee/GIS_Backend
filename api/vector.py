from fastapi import APIRouter

from schemas.vector_schema import VectorOperation
from services.vector_services import (
    union_features,
    intersection_features,
    difference_features,
    symdifference_features
)

router = APIRouter(
    prefix="/vector",
    tags=["Vector Operations"]
)


@router.post("/union")
def union(operation: VectorOperation):
    return union_features(operation.feature_ids)


@router.post("/intersection")
def intersection(operation: VectorOperation):
    return intersection_features(operation.feature_ids)


@router.post("/difference")
def difference(operation: VectorOperation):
    return difference_features(operation.feature_ids)


@router.post("/symdifference")
def symdifference(operation: VectorOperation):
    return symdifference_features(operation.feature_ids)
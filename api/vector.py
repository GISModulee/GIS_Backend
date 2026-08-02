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
def union(operation: VectorOperation, db: Session = Depends(get_db)):
    return union_features(operation.case_id, operation.feature_numbers, db)


@router.post("/intersection")
def intersection(operation: VectorOperation, db: Session = Depends(get_db)):
    return intersection_features(operation.case_id, operation.feature_numbers, db)


@router.post("/difference")
def difference(operation: VectorOperation, db: Session = Depends(get_db)):
    return difference_features(operation.case_id, operation.feature_numbers, db)


@router.post("/symdifference")
def symdifference(operation: VectorOperation, db: Session = Depends(get_db)):
    return symdifference_features(operation.case_id, operation.feature_numbers, db)


@router.post("/buffer")
def buffer(operation: BufferOperation, db: Session = Depends(get_db)):
    return buffer_feature(
        operation.case_id,
        operation.feature_number,
        operation.distance,
        db,
    )


@router.post("/centroid")
def centroid(operation: CentroidOperation, db: Session = Depends(get_db)):
    return centroid_feature(operation.case_id, operation.feature_number, db)


@router.post("/convex-hull")
def convex(operation: ConvexHullOperation, db: Session = Depends(get_db)):
    return convex_hull(operation.case_id, operation.feature_numbers, db)

from pydantic import BaseModel
from typing import List


class VectorOperation(BaseModel):
    case_id: int
    feature_numbers: List[int]


class BufferOperation(BaseModel):
    case_id: int
    feature_number: int
    distance: float


class CentroidOperation(BaseModel):
    case_id: int
    feature_number: int


class ConvexHullOperation(BaseModel):
    case_id: int
    feature_numbers: List[int]
from pydantic import BaseModel
from typing import List


class VectorOperation(BaseModel):
    case_id: int
    feature_numbers: List[int]
    layer_name: str | None = None


class BufferOperation(BaseModel):
    case_id: int
    feature_number: int
    distance: float
    layer_name: str | None = None


class CentroidOperation(BaseModel):
    case_id: int
    feature_number: int
    layer_name: str | None = None


class ConvexHullOperation(BaseModel):
    case_id: int
    feature_numbers: List[int]
    layer_name: str | None = None

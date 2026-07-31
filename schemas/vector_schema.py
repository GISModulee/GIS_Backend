from pydantic import BaseModel
from typing import List
 
 
class VectorOperation(BaseModel):
    feature_ids: List[int]
 
 
 
class BufferOperation(BaseModel):
    feature_id: int
    distance: float
 
 
class CentroidOperation(BaseModel):
    feature_id: int
 
 
class ConvexHullOperation(BaseModel):
    feature_ids: list[int]
 
from pydantic import BaseModel
from typing import List
 
 
class VectorOperation(BaseModel):
    feature_ids: List[int]
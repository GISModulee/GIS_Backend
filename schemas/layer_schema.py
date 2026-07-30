from pydantic import BaseModel
from typing import Optional


class LayerCreate(BaseModel):
    case_id: Optional[int] = None
    name: str
    layer_type: str
    visible: bool = True


class LayerPatch(BaseModel):
    name: Optional[str] = None
    layer_type: Optional[str] = None
    visible: Optional[bool] = None


class LayerResponse(BaseModel):
    id: int
    case_id: Optional[int] = None
    name: str
    layer_type: str
    visible: bool

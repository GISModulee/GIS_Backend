from pydantic import BaseModel
from typing import Optional


# ===================================================
# CREATE / UPDATE LAYER
# ===================================================

class LayerCreate(BaseModel):

    case_id: Optional[int] = None

    name: str

    layer_type: str

    visible: bool = True


# ===================================================
# PATCH LAYER
# ===================================================

class LayerPatch(BaseModel):

    name: Optional[str] = None

    layer_type: Optional[str] = None

    visible: Optional[bool] = None


# ===================================================
# RESPONSE
# ===================================================

class LayerResponse(BaseModel):

    id: int

    case_id: Optional[int] = None

    name: str

    layer_type: str

    visible: bool

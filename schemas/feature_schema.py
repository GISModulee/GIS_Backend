from pydantic import BaseModel
from typing import Dict, Any, Optional


# ===================================================
# CREATE FEATURE
# ===================================================

class FeatureCreate(BaseModel):
    case_id: Optional[int] = None
    layer_id: Optional[int] = None

    name: str

    # Existing GeoJSON (Polygon, LineString, Point)
    geometry: Optional[Dict[str, Any]] = None

    # New
    geometry_type: str = "Polygon"

    # Only used for circles
    center: Optional[Dict[str, float]] = None
    radius: Optional[float] = None

    properties: Dict[str, Any] = {}

    created_by: Optional[int] = None


# ===================================================
# PATCH FEATURE
# ===================================================

class FeaturePatch(BaseModel):
    name: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None

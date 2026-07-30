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

    # NOTE: `created_by` intentionally NOT accepted from the client.
    # It's derived server-side from the authenticated user
    # (current_user['user_id']) and passed as an explicit argument to
    # feature_service.create_feature(feature, created_by) instead —
    # accepting it here would let any client claim any user created
    # a feature.


# ===================================================
# PATCH FEATURE
# ===================================================

class FeaturePatch(BaseModel):
    name: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None

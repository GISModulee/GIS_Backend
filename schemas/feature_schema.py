from datetime import datetime

from pydantic import BaseModel, Field
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

    properties: Dict[str, Any] = Field(default_factory=dict)

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


class FeatureResponse(BaseModel):
    id: int
    feature_number: int
    case_id: int
    layer_id: int
    name: str
    geometry_type: str
    radius: float | None = None
    geometry: Dict[str, Any] | None = None
    properties: Dict[str, Any] | None = None
    created_by: int | None = None
    created_at: datetime
    updated_at: datetime | None = None


class FeatureCreateResponse(BaseModel):
    success: bool
    feature_id: int
    feature_number: int
    case_id: int
    layer_id: int


class FeatureActionResponse(BaseModel):
    success: bool
    message: str

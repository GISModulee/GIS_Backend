from datetime import datetime

from pydantic import BaseModel, Field, field_validator
from typing import Dict, Any, Literal, Optional

from utils.constants import (
    ALLOWED_MODULE_SLUGS,
    DEFAULT_MODULE_SLUG,
    MAX_MODULE_SLUG_LENGTH,
    MODULE_SLUG_EMPTY,
    MODULE_SLUG_INVALID,
    MODULE_SLUG_NOT_FOUND,
    MODULE_SLUG_REQUIRED,
    MODULE_SLUG_TOO_LONG,
)


# ===================================================
# CREATE FEATURE
# ===================================================

class FeatureCreate(BaseModel):
    case_id: Optional[int] = None
    layer_id: Optional[int] = None

    name: str

    # Origin module that created this feature. Defaults to gis so
    # existing GIS routes keep working unchanged; email-dump and
    # telecom-analysis integrations set it explicitly.
    module_slug: str = DEFAULT_MODULE_SLUG

    # Existing GeoJSON (Polygon, LineString, Point)
    geometry: Optional[Dict[str, Any]] = None

    # # New
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

    @field_validator("module_slug", mode="before")
    @classmethod
    def _validate_module_slug(cls, value):
        if value is None:
            raise ValueError(MODULE_SLUG_REQUIRED)
        if not isinstance(value, str):
            raise ValueError(MODULE_SLUG_INVALID)
        slug = value.strip()
        if not slug:
            raise ValueError(MODULE_SLUG_EMPTY)
        if len(slug) > MAX_MODULE_SLUG_LENGTH:
            raise ValueError(MODULE_SLUG_TOO_LONG)
        if slug not in ALLOWED_MODULE_SLUGS:
            raise ValueError(MODULE_SLUG_NOT_FOUND)
        return slug


# ===================================================
# PATCH FEATURE
# ===================================================

class FeaturePatch(BaseModel):
    name: str | None = None
    properties: dict | None = None
    layer_id: int | None = None


class MeasurementFeatureCreate(BaseModel):
    geometry: Dict[str, Any]
    measurement_type: Literal["straight", "walking"]
    distance_meters: float = Field(..., ge=0)


class FeatureResponse(BaseModel):
    id: int
    feature_number: int
    case_id: int
    layer_id: int | None = None
    module_slug: str
    name: str
    geometry_type: str
    radius: float | None = None
    geometry: Dict[str, Any] | None = None
    properties: Dict[str, Any] | None = None
    created_by: int | None = None
    created_at: datetime
    updated_at: datetime | None = None
    has_comments: bool = False


# ===================================================
# LIST LAYER FEATURES (summary view — no geometry/metadata)
# ===================================================

class FeatureSummaryResponse(BaseModel):
    id: int
    feature_number: int
    case_id: int
    layer_id: int | None = None
    module_slug: str
    has_comments: bool = False


class FeatureCreateResponse(BaseModel):
    success: bool
    feature_id: int
    feature_number: int
    case_id: int
    layer_id: int


class FeatureActionResponse(BaseModel):
    success: bool
    message: str

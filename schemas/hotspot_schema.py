from typing import Literal

from pydantic import BaseModel, Field, field_validator


class HotspotSearchRequest(BaseModel):
    case_id: int = Field(..., gt=0)
    layer_id: int = Field(..., gt=0)
    feature_number: int = Field(..., gt=0)
    category_groups: list[str] = Field(default_factory=list, max_length=20)
    range_meters: int | None = None
    limit: int = Field(default=100, ge=1, le=1000)

    @field_validator("category_groups", mode="before")
    @classmethod
    def validate_category_groups(cls, value) -> list[str]:
        if not value:
            raise ValueError("Select at least one hotspot category")
        return value

    @field_validator("range_meters")
    @classmethod
    def validate_range_meters(cls, value: int | None) -> int | None:
        if value is not None and not 1 <= value <= 50000:
            raise ValueError("Enter a range within 50 km")
        return value


class HotspotItem(BaseModel):
    osm_id: int
    name: str | None = None
    type: str
    category: str
    priority: Literal["high", "medium", "low"]
    distance_m: float | None = None
    coordinates: list[float] = Field(..., min_length=2, max_length=2)


class HotspotRiskZone(BaseModel):
    zone_id: str
    priority: Literal["high", "medium"]
    center: list[float] = Field(..., min_length=2, max_length=2)
    radius_m: int
    hotspot_count: int
    high_count: int
    medium_count: int


class HotspotSearchResponse(BaseModel):
    status: str
    case_id: int
    layer_id: int
    feature_number: int
    count: int
    category_counts: dict[str, int] = Field(default_factory=dict)
    items: list[HotspotItem]
    risk_zones: list[HotspotRiskZone] = Field(default_factory=list)


class HotspotSaveRequest(BaseModel):
    case_id: int = Field(..., gt=0)
    source_layer_id: int = Field(..., gt=0)
    source_feature_number: int = Field(..., gt=0)
    target_layer_id: int | None = Field(default=None, gt=0)
    layer_name: str | None = Field(default=None, max_length=100)
    hotspots: list[HotspotItem] = Field(..., min_length=1, max_length=1000)


class HotspotSaveResponse(BaseModel):
    success: bool
    case_id: int
    layer_id: int
    saved_count: int
    skipped_count: int
    feature_ids: list[int]
    feature_numbers: list[int]

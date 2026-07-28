from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator


Longitude = Annotated[float, Field(ge=-180, le=180)]
Latitude = Annotated[float, Field(ge=-90, le=90)]


class GeometryInput(BaseModel):
    type: Literal["Point", "LineString", "Polygon", "Circle", "Rectangle"]
    coordinates: list
    radius: float | None = Field(default=None, gt=0, le=100_000)

    @model_validator(mode="after")
    def validate_shape_fields(self):
        if self.type == "Circle" and self.radius is None:
            raise ValueError("radius is required for Circle geometry")
        if self.type not in {"Circle", "LineString"} and self.radius is not None:
            raise ValueError("radius is supported only for Circle and LineString")
        return self


class VectorOperationInput(BaseModel):
    shape_a: GeometryInput
    shape_b: GeometryInput
    operation: Literal["union", "intersection", "difference"]


class GeoSearchRequest(BaseModel):
    single_shape: GeometryInput | None = None
    vector_op: VectorOperationInput | None = None
    keywords: list[str] = Field(default_factory=list, max_length=10)
    start_date: datetime | None = None
    end_date: datetime | None = None
    max_results: int = Field(default=50, ge=1, le=100)
    h3_resolution: int = Field(default=7, ge=3, le=10)

    @model_validator(mode="after")
    def validate_request(self):
        if (self.single_shape is None) == (self.vector_op is None):
            raise ValueError("provide exactly one of single_shape or vector_op")
        cleaned = []
        seen = set()
        for keyword in self.keywords:
            keyword = keyword.strip()
            if not keyword:
                raise ValueError("keywords cannot contain blank values")
            if len(keyword) > 80:
                raise ValueError("each keyword must be at most 80 characters")
            key = keyword.casefold()
            if key not in seen:
                seen.add(key)
                cleaned.append(keyword)
        self.keywords = cleaned
        if self.start_date and self.end_date:
            start = self.start_date
            end = self.end_date
            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
            if end.tzinfo is None:
                end = end.replace(tzinfo=timezone.utc)
            if start > end:
                raise ValueError("start_date must be before or equal to end_date")
        return self


class NewsItem(BaseModel):
    id: str
    title: str
    summary: str | None = None
    url: str
    source: str
    provider: str
    published_at: datetime | None = None
    lat: float
    lon: float
    coordinate_type: Literal["area_display_point"] = "area_display_point"
    area_relevance: int = Field(ge=0, le=100)
    trust_score: int = Field(ge=0, le=100)
    location_evidence: list[str] = Field(default_factory=list)


class SourceStatus(BaseModel):
    status: Literal["success", "empty", "timeout", "rate_limited", "error"]
    results: int = 0
    accepted_results: int = 0
    detail: str | None = None


class GeoSearchResponse(BaseModel):
    status: Literal["success", "partial_success", "upstream_unavailable"]
    total_results: int
    h3_cells_count: int
    execution_time_seconds: float
    area: dict
    sources: dict[str, SourceStatus]
    items: list[NewsItem]

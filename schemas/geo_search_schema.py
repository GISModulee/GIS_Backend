from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from utils.constants import (
    GEO_SEARCH_PROVIDER_EMPTY,
    GEO_SEARCH_PROVIDER_ERROR,
    GEO_SEARCH_PROVIDER_RATE_LIMITED,
    GEO_SEARCH_PROVIDER_TIMEOUT,
    GEO_SEARCH_STATUS_PARTIAL_SUCCESS,
    GEO_SEARCH_STATUS_SUCCESS,
    GEO_SEARCH_STATUS_UPSTREAM_UNAVAILABLE,
)


class GeoSearchRequest(BaseModel):
    case_id: int = Field(..., gt=0)
    layer_id: int = Field(..., gt=0)
    feature_id: int = Field(..., gt=0)
    keywords: list[str] = Field(default_factory=list, max_length=10)
    start_date: datetime | None = None
    end_date: datetime | None = None
    max_results: int = Field(default=10, ge=1, le=50)

    @model_validator(mode="after")
    def validate_request(self):
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
    status: Literal[
        GEO_SEARCH_STATUS_SUCCESS,
        GEO_SEARCH_PROVIDER_EMPTY,
        GEO_SEARCH_PROVIDER_TIMEOUT,
        GEO_SEARCH_PROVIDER_RATE_LIMITED,
        GEO_SEARCH_PROVIDER_ERROR,
    ]
    results: int = 0
    accepted_results: int = 0
    detail: str | None = None


class GeoSearchSelection(BaseModel):
    case_id: int
    layer_id: int
    feature_id: int


class GeoSearchResponse(BaseModel):
    status: Literal[
        GEO_SEARCH_STATUS_SUCCESS,
        GEO_SEARCH_STATUS_PARTIAL_SUCCESS,
        GEO_SEARCH_STATUS_UPSTREAM_UNAVAILABLE,
    ]
    total_results: int
    execution_time_seconds: float
    selection: GeoSearchSelection
    area: dict
    sources: dict[str, SourceStatus]
    items: list[NewsItem]

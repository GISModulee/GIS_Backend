from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class PointGeometry(BaseModel):
    type: Literal["Point"] = "Point"
    coordinates: tuple[float, float]


class GeoJSONFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    geometry: PointGeometry
    properties: dict[str, Any]


class GeoJSONFeatureCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[GeoJSONFeature] = Field(default_factory=list)


class AircraftState(BaseModel):
    icao24: str
    callsign: str | None = None
    origin_country: str | None = None
    longitude: float
    latitude: float
    barometric_altitude: float | None = None
    geometric_altitude: float | None = None
    velocity: float | None = None
    heading: float | None = None
    vertical_rate: float | None = None
    on_ground: bool
    last_contact: datetime | None = None
    time_position: datetime | None = None
    squawk: str | None = None
    category: int | None = None


class SatellitePosition(BaseModel):
    name: str
    norad_id: str | None = None
    longitude: float
    latitude: float
    altitude_km: float
    propagated_at: datetime

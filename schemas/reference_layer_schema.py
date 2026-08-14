from typing import Any

from pydantic import BaseModel


class ReferenceLayerResponse(BaseModel):
    id: int
    name: str
    layer_type: str
    description: str | None = None
    visible: bool


class ReferenceFeatureResponse(BaseModel):
    id: int
    name: str | None = None
    geometry: dict[str, Any]
    properties: dict[str, Any] = {}


class ReferenceFeatureCollectionResponse(BaseModel):
    type: str
    features: list[ReferenceFeatureResponse]
from pydantic import BaseModel
from typing import Dict, Any
from datetime import datetime


class ImageUploadResponse(BaseModel):
    id: str
    layer_id: int
    layer_name: str
    filename: str
    predictions_created: int
    data: Dict[str, Any]
    status: str


class ImageResponse(BaseModel):
    id: str
    layer_id: int
    filename: str
    raw_metadata: Dict[str, Any]
    created_at: datetime

    class Config:
        from_attributes = True


class LayerRenameRequest(BaseModel):
    name: str


class LayerActionResponse(BaseModel):
    id: int
    name: str
    status: str


class FeatureGeoJSON(BaseModel):
    type: str = "Feature"
    id: int
    layer_id: int
    name: str | None = None
    geometry: Dict[str, Any]  
    properties: Dict[str, Any]


class FeatureCollectionResponse(BaseModel):
    type: str = "FeatureCollection"
    features: list[FeatureGeoJSON]


class ErrorResponse(BaseModel):
    status: str = "error"
    detail: str
    request_id: str

from pydantic import BaseModel
from typing import Dict, Any
from datetime import datetime


class ImageUploadResponse(BaseModel):
    id: str
    layer_id: int
    layer_name: str
    filename: str
    predictions_created: int
    data: Dict[str, Any]
    status: str


class ImageResponse(BaseModel):
    id: str
    layer_id: int
    filename: str
    raw_metadata: Dict[str, Any]
    created_at: datetime

    class Config:
        from_attributes = True


class LayerRenameRequest(BaseModel):
    name: str


class LayerActionResponse(BaseModel):
    id: int
    name: str
    status: str


class FeatureGeoJSON(BaseModel):
    type: str = "Feature"
    id: int
    layer_id: int
    name: str | None = None
    geometry: Dict[str, Any]  
    properties: Dict[str, Any]


class FeatureCollectionResponse(BaseModel):
    type: str = "FeatureCollection"
    features: list[FeatureGeoJSON]


class ErrorResponse(BaseModel):
    status: str = "error"
    detail: str
    request_id: str

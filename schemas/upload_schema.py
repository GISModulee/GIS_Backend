from typing import Any

from pydantic import BaseModel


class CSVImportData(BaseModel):
    columns: list[str]
    total_rows: int
    rows: list[dict[str, Any]]


class RasterBounds(BaseModel):
    left: float
    bottom: float
    right: float
    top: float


class RasterImportData(BaseModel):
    width: int
    height: int
    bands: int
    crs: str
    bounds: RasterBounds


class LayerImportData(BaseModel):
    success: bool
    status: str
    layer_id: int
    layer_name: str
    imported_features: int
    message: str | None = None


class UploadResponse(BaseModel):
    success: bool
    case_id: int
    filename: str
    file_type: str
    data: CSVImportData | RasterImportData | LayerImportData | dict[str, Any]

import os
import uuid
import hashlib
import json
import pandas as pd
import geopandas as gpd
import rasterio

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from models.model import Layer
from schemas.feature_schema import FeatureCreate
from services.feature.feature_service import create_features_batch
from utils.constants import (
    CASE_ID_REQUIRED,
    CSV_PARSE_FAILED_TEMPLATE,
    FILE_NAME_INVALID,
    GEOJSON_FEATURES_ARRAY_INVALID,
    IMPLEMENTATION_MISSING,
    JSON_GEOJSON_EXPECTED,
    JSON_OBJECT_EXPECTED,
    JSON_PARSE_FAILED_TEMPLATE,
    KML_PARSE_FAILED_TEMPLATE,
    LAYER_CREATE_FAILED,
    LAYER_DUPLICATE_NAME_TEMPLATE,
    LAYER_DUPLICATE_SUFFIX_IMPORT,
    TIFF_READ_FAILED_TEMPLATE,
    UPLOAD_TYPE_UNSUPPORTED_TEMPLATE,
)
from utils.logger import logger
from utils.exceptions import (
    BadRequestError,
    ConflictError,
    NotImplementedError_,
    ServiceUnavailableError,
    UnsupportedMediaTypeError,
    UnprocessableEntityError,
)

class BaseExtractor:
    def extract(self, *, file_path, filename, case_id, layer_name, created_by, db):
        raise NotImplementedError_(
            IMPLEMENTATION_MISSING
        )


class CSVExtractor(BaseExtractor):
    def extract(self, *, file_path, **_ignored):
        try:
            df = pd.read_csv(file_path)
        except Exception as e:
            logger.error(f"Failed to parse CSV | file_path={file_path} | error={e}", exc_info=True)
            raise UnprocessableEntityError(CSV_PARSE_FAILED_TEMPLATE.format(reason=e)) from e

        return {
            "columns": list(df.columns),
            "total_rows": len(df),
            "rows": df.to_dict(orient="records")
        }


class TiffExtractor(BaseExtractor):
    def extract(self, *, file_path, **_ignored):
        try:
            with rasterio.open(file_path) as src:
                bounds = src.bounds
                return {
                    "width": src.width,
                    "height": src.height,
                    "bands": src.count,
                    "crs": str(src.crs),
                    "bounds": {
                        "left": bounds.left,
                        "bottom": bounds.bottom,
                        "right": bounds.right,
                        "top": bounds.top
                    }
                }
        except Exception as e:
            logger.error(f"Failed to read TIFF | file_path={file_path} | error={e}", exc_info=True)
            raise UnprocessableEntityError(TIFF_READ_FAILED_TEMPLATE.format(reason=e)) from e


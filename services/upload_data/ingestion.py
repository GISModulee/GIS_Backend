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
from services.upload_data.geometry import remove_z_coordinates

SUPPORTED_GEOMETRY_TYPES = {
    "Point",
    "MultiPoint",
    "LineString",
    "MultiLineString",
    "Polygon",
    "MultiPolygon",
}

# INGEST FEATURES (batched — one DB round-trip, not one per feature)
# ===================================================
# UPDATED: previously called create_feature() once per row inside the
# loop (one lock + one commit per feature — very slow for large
# files). Now collects every feature into a plain list first, then
# hands the whole list to create_features_batch() which does ONE
# advisory lock, ONE feature_number lookup, and ONE commit for the
# entire file.

def _ingest_features(case_id, layer_id, feature_iter, created_by, db):
    """
    feature_iter yields (name, geometry, properties) tuples for each
    feature to import. Returns created feature IDs and numbers.
    """
    collected = []

    for name, geometry, properties in feature_iter:

        if not isinstance(geometry, dict):
            continue

        geometry_type = geometry.get("type")
        if geometry_type not in SUPPORTED_GEOMETRY_TYPES:
            logger.warning(
                "Skipping unsupported import geometry | case_id=%s | layer_id=%s | geometry_type=%s",
                case_id,
                layer_id,
                geometry_type,
            )
            continue

        geometry = remove_z_coordinates(geometry)

        collected.append({
            "name": name or f"Feature {len(collected) + 1}",
            "geometry": geometry,
            "geometry_type": geometry_type,
            "properties": properties,
        })

    created = create_features_batch(
        collected,
        case_id,
        layer_id,
        db,
        created_by,
    )

    return created

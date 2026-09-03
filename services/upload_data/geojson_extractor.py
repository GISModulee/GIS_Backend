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
from services.upload_data.base_extractors import BaseExtractor
from services.upload_data.storage import _check_duplicate_import, _hash_file, _resolve_case_id, _create_import_layer, _resolve_layer_name
from services.upload_data.ingestion import _ingest_features

class GeoJSONExtractor(BaseExtractor):
    # Accepts standard GeoJSON from either .json or .geojson files,
    # as well as application JSON containing a `single_shape`
    # GeoJSON geometry. Mirrors
    # KMLExtractor's flow (dedup by file hash, one layer per file,
    # one create_feature call per feature) but parses natively with
    # `json` instead of geopandas, since GeoJSON needs no driver
    # detection.
    def extract(
        self,
        *,
        file_path,
        filename,
        case_id,
        layer_name,
        created_by,
        db,
        batch_size,
        on_batch_created=None,
    ):

        case_id = _resolve_case_id(case_id, created_by)

        file_hash = _hash_file(file_path)

        duplicate_response = _check_duplicate_import(case_id, file_hash, "JSON", db)
        if duplicate_response:
            return duplicate_response

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                geojson = json.load(f)
        except Exception as e:
            logger.error(f"Failed to parse JSON | case_id={case_id} | filename={filename} | error={e}", exc_info=True)
            raise UnprocessableEntityError(JSON_PARSE_FAILED_TEMPLATE.format(reason=e)) from e

        if not isinstance(geojson, dict):
            raise UnprocessableEntityError(
                JSON_OBJECT_EXPECTED
            )

        json_type = geojson.get("type")
        if json_type == "FeatureCollection":
            raw_features = geojson.get("features", [])
        elif json_type == "Feature":
            raw_features = [geojson]
        elif json_type in {
            "Point",
            "MultiPoint",
            "LineString",
            "MultiLineString",
            "Polygon",
            "MultiPolygon",
        }:
            raw_features = [{
                "type": "Feature",
                "geometry": geojson,
                "properties": {},
            }]
        elif isinstance(geojson.get("single_shape"), dict):
            raw_features = [{
                "type": "Feature",
                "geometry": geojson["single_shape"],
                "properties": {
                    key: value
                    for key, value in geojson.items()
                    if key != "single_shape"
                },
            }]
        else:
            raise UnprocessableEntityError(
                JSON_GEOJSON_EXPECTED
            )

        if not isinstance(raw_features, list):
            raise UnprocessableEntityError(
                GEOJSON_FEATURES_ARRAY_INVALID
            )

        resolved_layer_name = _resolve_layer_name(layer_name, filename)

        layer_response = _create_import_layer(
            case_id=case_id,
            name=resolved_layer_name,
            file_hash=file_hash,
            db=db
        )

        layer_id = layer_response["layer_id"]

        def _geojson_features():
            for raw_feature in raw_features:
                if not isinstance(raw_feature, dict):
                    continue
                geometry = raw_feature.get("geometry")
                if geometry is None:
                    continue
                properties = raw_feature.get("properties") or {}
                name = properties.get("Name") or properties.get("name")
                yield name, geometry, properties

        imported_features = _ingest_features(
            case_id,
            layer_id,
            _geojson_features(),
            created_by,
            db,
            batch_size,
            on_batch_created,
        )

        return {
            "success": True,
            "status": "imported",
            "layer_id": layer_id,
            "layer_name": resolved_layer_name,
            "imported_features": imported_features,
        }

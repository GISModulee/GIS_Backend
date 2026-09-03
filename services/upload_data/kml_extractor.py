import os
import uuid
import hashlib
import json
import xml.etree.ElementTree as ET
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


def _parse_coordinate_pairs(text):
    coordinates = []
    for token in (text or "").replace("\n", " ").split():
        parts = token.split(",")
        if len(parts) < 2:
            continue
        try:
            coordinates.append([float(parts[0]), float(parts[1])])
        except ValueError:
            logger.warning("Skipping malformed KML coordinate | value=%s", token)
    return coordinates


def _placemark_name(placemark):
    name = placemark.find("./{*}name")
    return name.text.strip() if name is not None and name.text else None


def _placemark_geometry(placemark):
    point = placemark.find(".//{*}Point/{*}coordinates")
    if point is not None and point.text:
        coordinates = _parse_coordinate_pairs(point.text)
        if coordinates:
            return {"type": "Point", "coordinates": coordinates[0]}

    line = placemark.find(".//{*}LineString/{*}coordinates")
    if line is not None and line.text:
        coordinates = _parse_coordinate_pairs(line.text)
        if coordinates:
            return {"type": "LineString", "coordinates": coordinates}

    polygon = placemark.find(".//{*}Polygon/{*}outerBoundaryIs/{*}LinearRing/{*}coordinates")
    if polygon is not None and polygon.text:
        coordinates = _parse_coordinate_pairs(polygon.text)
        if coordinates:
            return {"type": "Polygon", "coordinates": [coordinates]}

    return None


def _parse_kml_features(file_path):
    root = ET.parse(file_path).getroot()
    for placemark in root.findall(".//{*}Placemark"):
        geometry = _placemark_geometry(placemark)
        if geometry is None:
            continue
        yield _placemark_name(placemark), geometry, {}


class KMLExtractor(BaseExtractor):
    # `layer_name`: optional. If provided, used as-is for the new
    # import layer. If omitted, derives the name from the uploaded
    # file's basename.
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

        duplicate_response = _check_duplicate_import(case_id, file_hash, "KML", db)
        if duplicate_response:
            return duplicate_response

        try:
            gdf = gpd.read_file(file_path)
        except Exception as e:
            logger.error(f"Failed to parse KML | case_id={case_id} | filename={filename} | error={e}", exc_info=True)
            raise UnprocessableEntityError(KML_PARSE_FAILED_TEMPLATE.format(reason=e)) from e

        resolved_layer_name = _resolve_layer_name(layer_name, filename)

        layer_response = _create_import_layer(
            case_id=case_id,
            name=resolved_layer_name,
            file_hash=file_hash,
            db=db
        )

        layer_id = layer_response["layer_id"]

        def _geopandas_features():
            for _, row in gdf.iterrows():
                if row.geometry is None:
                    continue
                geometry = row.geometry.__geo_interface__
                name = row.get("Name") or row.get("name")
                properties = row.drop(labels="geometry").fillna("").to_dict()
                yield name, geometry, properties

        feature_iter = _geopandas_features()
        if gdf.empty:
            feature_iter = _parse_kml_features(file_path)

        imported_features = _ingest_features(
            case_id,
            layer_id,
            feature_iter,
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

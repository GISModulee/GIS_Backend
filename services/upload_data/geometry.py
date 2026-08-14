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

def strip_point(point):
    return point[:2]


def remove_z_coordinates(geometry):

    geometry = geometry.copy()

    geom_type = geometry["type"]

    if geom_type == "Point":
        geometry["coordinates"] = strip_point(geometry["coordinates"])

    elif geom_type == "LineString":
        geometry["coordinates"] = [
            strip_point(point)
            for point in geometry["coordinates"]
        ]

    elif geom_type == "Polygon":
        geometry["coordinates"] = [
            [
                strip_point(point)
                for point in ring
            ]
            for ring in geometry["coordinates"]
        ]

    elif geom_type == "MultiPoint":
        geometry["coordinates"] = [
            strip_point(point)
            for point in geometry["coordinates"]
        ]

    elif geom_type == "MultiLineString":
        geometry["coordinates"] = [
            [
                strip_point(point)
                for point in line
            ]
            for line in geometry["coordinates"]
        ]

    elif geom_type == "MultiPolygon":
        geometry["coordinates"] = [
            [
                [
                    strip_point(point)
                    for point in ring
                ]
                for ring in polygon
            ]
            for polygon in geometry["coordinates"]
        ]

    return geometry

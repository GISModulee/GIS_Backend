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


# ===================================================
# UPLOAD FOLDER
# ===================================================

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ===================================================
# FILENAME SANITIZATION
# ===================================================
# FIX (issue #4 in review): file.filename comes straight from the
# client with no sanitization. A crafted filename (e.g. containing
# "../../") could previously write outside UPLOAD_FOLDER via
# os.path.join(UPLOAD_FOLDER, file.filename). os.path.basename()
# strips any directory component the client tries to sneak in, and
# the random prefix avoids collisions/overwrites between concurrent
# uploads that happen to share a filename. The ORIGINAL filename is
# still used everywhere else (layer naming, hashing display, logs) —
# only the on-disk path uses the sanitized version.
def _sanitize_filename(filename: str) -> str:
    base = os.path.basename((filename or "").replace("\\", "/"))
    if not base or base in (".", ".."):
        raise BadRequestError(FILE_NAME_INVALID)
    return f"{uuid.uuid4().hex}_{base}"


# ===================================================
# SHARED IMPORT HELPERS
# ===================================================
# Both KML and JSON extractors need: (1) resolve/default the case,
# (2) hash the file and short-circuit on duplicate imports, (3)
# create a single layer for the file. Pulled out here so there's one
# implementation to maintain instead of copy-pasting in each class.

def _resolve_case_id(case_id, _created_by):
    if case_id is None:
        raise BadRequestError(CASE_ID_REQUIRED)
    return case_id


def _hash_file(file_path):
    with open(file_path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _check_duplicate_import(case_id, file_hash, source_label, db):
    """
    Returns the short-circuit response dict if this exact file was
    already imported into this case, else None.
    """
    existing_layer = db.scalar(
        select(Layer).where(
            Layer.case_id == case_id,
            Layer.file_hash == file_hash,
            Layer.layer_type == "import",
        ).limit(1)
    )

    if not existing_layer:
        return None

    logger.info(
        f"Duplicate {source_label} import detected — reusing existing layer | "
        f"case_id={case_id} | layer_id={existing_layer.id} | file_hash={file_hash}"
    )
    return {
        "success": True,
        "status": "already_imported",
        "layer_id": existing_layer.id,
        "layer_name": existing_layer.name,
        "imported_features": 0,
        "message": "This file was already imported into this case — no new layer created."
    }
def _create_import_layer(case_id, name, file_hash, db):
    try:
        existing_id = db.scalar(
            select(Layer.id).where(
                Layer.case_id == case_id,
                Layer.name == name,
            ).limit(1)
        )
        if existing_id is not None:
            raise ConflictError(
                LAYER_DUPLICATE_NAME_TEMPLATE.format(
                    name=name,
                    suffix=LAYER_DUPLICATE_SUFFIX_IMPORT,
                )
            )

        record = Layer(
            case_id=case_id,
            name=name,
            layer_type="import",
            visible=True,
            file_hash=file_hash,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return {
            "success": True,
            "layer_id": record.id,
            "message": "Layer created successfully",
        }

    except ConflictError:
        raise

    except IntegrityError as e:
        db.rollback()
        raise ConflictError(
            LAYER_DUPLICATE_NAME_TEMPLATE.format(
                name=name,
                suffix=LAYER_DUPLICATE_SUFFIX_IMPORT,
            )
        ) from e

    except SQLAlchemyError as e:
        db.rollback()
        raise ServiceUnavailableError(LAYER_CREATE_FAILED) from e


def _resolve_layer_name(layer_name, filename):
    return layer_name if layer_name else os.path.splitext(filename)[0]

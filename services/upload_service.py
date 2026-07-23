import os
import uuid
import hashlib
import pandas as pd
import geopandas as gpd
import rasterio

from fastapi import UploadFile

from schemas.feature_schema import FeatureCreate
from services.feature_service import create_feature
from services.case_service import create_untitled_case
from services.layer_service import (
    create_import_layer,
    get_import_layer_by_hash,
)
from utils.logger import logger
from utils.exception_handler import BadRequestError, UnprocessableEntityError


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
        raise BadRequestError("Invalid filename")
    return f"{uuid.uuid4().hex}_{base}"


# ===================================================
# PROCESS UPLOADED FILE
# ===================================================
def process_upload(
    case_id: int,
    file: UploadFile,
    layer_name: str | None = None,
    created_by: int | None = None,
):

    safe_name = _sanitize_filename(file.filename)
    file_path = os.path.join(UPLOAD_FOLDER, safe_name)

    # file.file is the underlying SpooledTemporaryFile — .read() here
    # is a plain synchronous call (UploadFile.read() is async and
    # would require `await`, which we no longer have in this function).
    with open(file_path, "wb") as f:
        f.write(file.file.read())

    extension = file.filename.split(".")[-1].lower()

    # -------------------------------------------------

    if extension == "csv":

        data = extract_csv(file_path)

    elif extension == "kml":

        data = extract_kml(
            case_id=case_id,
            file_path=file_path,
            filename=file.filename,
            layer_name=layer_name,
            created_by=created_by,
        )

    elif extension in ["tif", "tiff"]:

        data = extract_tiff(file_path)

    else:

        # FIX (issue #10 in review): previously returned
        # {"success": False, "message": ...} with an HTTP 200 status,
        # which any caller that only checks status code would miss.
        # Raising here lets the global AppException handler return a
        # proper 400 with the same detail message.
        raise BadRequestError(f"Unsupported file type: {extension}")

    return {
        "success": True,
        "case_id": case_id,
        "filename": file.filename,
        "file_type": extension,
        "data": data
    }


# ===================================================
# CSV
# ===================================================

def extract_csv(file_path):

    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        logger.error(f"Failed to parse CSV | file_path={file_path} | error={e}", exc_info=True)
        raise UnprocessableEntityError(f"Failed to parse CSV: {e}") from e

    return {
        "columns": list(df.columns),
        "total_rows": len(df),
        "rows": df.to_dict(orient="records")
    }


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


# ===================================================
# KML IMPORT
# ===================================================
# `layer_name`: optional. If provided, used as-is for the new import
# layer. If omitted, falls back to the previous behavior of deriving
# the name from the uploaded file's basename.
def extract_kml(case_id, file_path, filename, layer_name=None, created_by=None):

    # ---------------------------------------------
    # Always use default case if frontend sends null
    # ---------------------------------------------

    if case_id is None:
        case_id = create_untitled_case(created_by)

    # ---------------------------------------------
    # Duplicate-import check: hash the file's bytes and see if
    # this exact file was already imported into this case. If so,
    # short-circuit — don't create a second layer or re-import
    # every feature again.
    # ---------------------------------------------

    with open(file_path, "rb") as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()

    existing_layer = get_import_layer_by_hash(case_id, file_hash)

    if existing_layer:
        logger.info(
            f"Duplicate KML import detected — reusing existing layer | "
            f"case_id={case_id} | layer_id={existing_layer['id']} | file_hash={file_hash}"
        )
        return {
            "success": True,
            "status": "already_imported",
            "layer_id": existing_layer["id"],
            "layer_name": existing_layer["name"],
            "imported_features": 0,
            "message": "This file was already imported into this case — no new layer created."
        }

    # ---------------------------------------------
    # Create ONE layer for this uploaded file
    # ---------------------------------------------

    # FIX (issue #10 in review): parsing failures used to be caught by
    # a blanket `except Exception` around this whole function and
    # returned as {"success": False, "error": ...} with HTTP 200.
    # Narrowed to just the parse step, and raises a proper 422 now.
    try:
        gdf = gpd.read_file(file_path)
    except Exception as e:
        logger.error(f"Failed to parse KML | case_id={case_id} | filename={filename} | error={e}", exc_info=True)
        raise UnprocessableEntityError(f"Failed to parse KML file: {e}") from e

    resolved_layer_name = layer_name if layer_name else os.path.splitext(filename)[0]

    layer_response = create_import_layer(
        case_id=case_id,
        name=resolved_layer_name,
        file_hash=file_hash
    )

    layer_id = layer_response["layer_id"]

    imported = 0

    # ---------------------------------------------
    # Import every geometry
    # ---------------------------------------------
    # NOTE: DB-layer failures from create_feature (BadRequestError,
    # ServiceUnavailableError, etc.) now propagate naturally instead
    # of being swallowed into a success:false response — see issue #10.

    for _, row in gdf.iterrows():

        if row.geometry is None:
            continue

        geometry = remove_z_coordinates(
            row.geometry.__geo_interface__
        )

        feature = FeatureCreate(
            case_id=case_id,
            layer_id=layer_id,
            name=row.get("Name") or row.get("name") or f"Feature {imported + 1}",
            geometry=geometry,
            geometry_type=geometry["type"],
            properties=row.drop(labels="geometry").fillna("").to_dict(),
        )

        create_feature(feature, created_by)

        imported += 1

    return {
        "success": True,
        "status": "imported",
        "layer_id": layer_id,
        "layer_name": resolved_layer_name,
        "imported_features": imported
    }


# ===================================================
# TIFF
# ===================================================

def extract_tiff(file_path):

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
        raise UnprocessableEntityError(f"Failed to read TIFF file: {e}") from e

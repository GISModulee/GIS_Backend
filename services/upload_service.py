import os
import uuid
import hashlib
import json
import pandas as pd
import geopandas as gpd
import rasterio

from fastapi import UploadFile

from schemas.feature_schema import FeatureCreate
from services.feature_service import create_feature
from services.layer_service import (
    create_import_layer,
    get_import_layer_by_hash,
)
from utils.logger import logger
from utils.exceptions import BadRequestError, NotImplementedError_, UnsupportedMediaTypeError, UnprocessableEntityError


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
# SHARED IMPORT HELPERS
# ===================================================
# Both KML and JSON extractors need: (1) resolve/default the case,
# (2) hash the file and short-circuit on duplicate imports, (3)
# create a single layer for the file. Pulled out here so there's one
# implementation to maintain instead of copy-pasting in each class.

def _resolve_case_id(case_id, _created_by):
    if case_id is None:
        raise BadRequestError("case_id is required")
    return case_id


def _hash_file(file_path):
    with open(file_path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _check_duplicate_import(case_id, file_hash, source_label, db):
    """
    Returns the short-circuit response dict if this exact file was
    already imported into this case, else None.
    """
    existing_layer = get_import_layer_by_hash(case_id, file_hash, db)

    if not existing_layer:
        return None

    logger.info(
        f"Duplicate {source_label} import detected — reusing existing layer | "
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
def _resolve_layer_name(layer_name, filename):
    return layer_name if layer_name else os.path.splitext(filename)[0]


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


def _ingest_features(case_id, layer_id, feature_iter, created_by, db):
    """
    feature_iter yields (name, geometry, properties) tuples for each
    feature to import. Returns the count of features imported.
    """
    imported = 0

    for name, geometry, properties in feature_iter:

        if geometry is None:
            continue

        geometry = remove_z_coordinates(geometry)

        feature = FeatureCreate(
            case_id=case_id,
            layer_id=layer_id,
            name=name or f"Feature {imported + 1}",
            geometry=geometry,
            geometry_type=geometry["type"],
            properties=properties,
        )

        create_feature(feature, db, created_by)

        imported += 1

    return imported


# ===================================================
# EXTRACTOR CLASSES (polymorphism / overriding)
# ===================================================
# BaseExtractor defines the contract: every extractor must implement
# .extract(). process_upload() calls extractor.extract() without
# caring which subclass it actually got — each subclass OVERRIDES
# extract() with its own file-type-specific logic. Adding a new file
# type later means adding one class + one registry entry, and never
# touching process_upload() or the other extractors again.

class BaseExtractor:
    def extract(self, *, file_path, filename, case_id, layer_name, created_by, db):
        raise NotImplementedError_(
            "Subclasses of BaseExtractor must override extract()"
        )


class CSVExtractor(BaseExtractor):
    def extract(self, *, file_path, **_ignored):
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


class KMLExtractor(BaseExtractor):
    # `layer_name`: optional. If provided, used as-is for the new
    # import layer. If omitted, derives the name from the uploaded
    # file's basename.
    def extract(self, *, file_path, filename, case_id, layer_name, created_by, db):

        case_id = _resolve_case_id(case_id, created_by)

        file_hash = _hash_file(file_path)

        duplicate_response = _check_duplicate_import(case_id, file_hash, "KML", db)
        if duplicate_response:
            return duplicate_response

        try:
            gdf = gpd.read_file(file_path)
        except Exception as e:
            logger.error(f"Failed to parse KML | case_id={case_id} | filename={filename} | error={e}", exc_info=True)
            raise UnprocessableEntityError(f"Failed to parse KML file: {e}") from e

        resolved_layer_name = _resolve_layer_name(layer_name, filename)

        layer_response = create_import_layer(
            case_id=case_id,
            name=resolved_layer_name,
            file_hash=file_hash,
            db=db
        )

        layer_id = layer_response["layer_id"]

        def _kml_features():
            for _, row in gdf.iterrows():
                if row.geometry is None:
                    continue
                geometry = row.geometry.__geo_interface__
                name = row.get("Name") or row.get("name")
                properties = row.drop(labels="geometry").fillna("").to_dict()
                yield name, geometry, properties

        imported = _ingest_features(case_id, layer_id, _kml_features(), created_by, db)

        return {
            "success": True,
            "status": "imported",
            "layer_id": layer_id,
            "layer_name": resolved_layer_name,
            "imported_features": imported
        }


class GeoJSONExtractor(BaseExtractor):
    # Accepts standard GeoJSON from either .json or .geojson files,
    # as well as application JSON containing a `single_shape`
    # GeoJSON geometry. Mirrors
    # KMLExtractor's flow (dedup by file hash, one layer per file,
    # one create_feature call per feature) but parses natively with
    # `json` instead of geopandas, since GeoJSON needs no driver
    # detection.
    def extract(self, *, file_path, filename, case_id, layer_name, created_by, db):

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
            raise UnprocessableEntityError(f"Failed to parse JSON file: {e}") from e

        if not isinstance(geojson, dict):
            raise UnprocessableEntityError(
                "Unsupported JSON structure: expected a JSON object"
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
                "Unsupported JSON structure: expected GeoJSON or a single_shape geometry"
            )

        if not isinstance(raw_features, list):
            raise UnprocessableEntityError(
                "Invalid GeoJSON: features must be an array"
            )

        resolved_layer_name = _resolve_layer_name(layer_name, filename)

        layer_response = create_import_layer(
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

        imported = _ingest_features(case_id, layer_id, _geojson_features(), created_by, db)

        return {
            "success": True,
            "status": "imported",
            "layer_id": layer_id,
            "layer_name": resolved_layer_name,
            "imported_features": imported
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
            raise UnprocessableEntityError(f"Failed to read TIFF file: {e}") from e


# Registry: extension -> extractor instance. Add a new file type by
# writing one class above + one line here. process_upload() below
# never needs to change again.
EXTRACTOR_REGISTRY = {
    "csv": CSVExtractor(),
    "kml": KMLExtractor(),
    "json": GeoJSONExtractor(),
    "geojson": GeoJSONExtractor(),
    "tif": TiffExtractor(),
    "tiff": TiffExtractor(),
}


# ===================================================
# PROCESS UPLOADED FILE
# ===================================================

async def process_upload(
    case_id: int,
    file: UploadFile,
    db,
    layer_name: str | None = None,
    created_by: int | None = None,
):

    safe_name = _sanitize_filename(file.filename)
    file_path = os.path.join(UPLOAD_FOLDER, safe_name)

    with open(file_path, "wb") as f:
        f.write(await file.read())

    extension = file.filename.split(".")[-1].lower()

    extractor = EXTRACTOR_REGISTRY.get(extension)
    if extractor is None:
        raise UnsupportedMediaTypeError(f"Unsupported file type: {extension}")

    data = extractor.extract(
        file_path=file_path,
        filename=file.filename,
        case_id=case_id,
        layer_name=layer_name,
        created_by=created_by,
        db=db,
    )

    return {
        "success": True,
        "case_id": case_id,
        "filename": file.filename,
        "file_type": extension,
        "data": data
    }

import json

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, DataError, SQLAlchemyError

from database.database import SessionLocal
from models.model import Feature, Layer
from schemas.feature_schema import FeatureCreate
from utils.logger import logger
from utils.exceptions import (
    NotFoundError,
    BadRequestError,
    UnprocessableEntityError,
    ServiceUnavailableError,
)

from services.case_service import create_untitled_case
from services.layer_service import create_untitled_layer


# ===================================================
# HELPERS
# ===================================================

def _create_auto_layer(case_id: int):
    return create_untitled_layer(case_id)


def _row_to_feature_dict(row):
    try:
        geometry = json.loads(row.geometry) if row.geometry else None
    except (TypeError, ValueError) as e:
        logger.error(f"Malformed geometry JSON for feature_id={row.id} | error={e}")
        geometry = None

    geometry_type = row.geometry_type
    if geometry and geometry.get("type") in {"Point", "LineString"}:
        geometry_type = geometry["type"]

    return {
        "id": row.id,
        "layer_id": row.layer_id,
        "name": row.name,
        "geometry_type": geometry_type,
        "radius": row.radius,
        "geometry": geometry,
        "properties": row.properties,
        "created_by": row.created_by,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _feature_select():
    return select(
        Feature.id,
        Feature.layer_id,
        Feature.name,
        Feature.geometry_type,
        Feature.radius,
        func.ST_AsGeoJSON(Feature.geom).label("geometry"),
        Feature.properties,
        Feature.created_by,
        Feature.created_at,
        Feature.updated_at,
    )


def _resolved_geometry_type(feature):
    """Use the actual GeoJSON type for points and lines only."""
    geometry = feature.geometry or {}
    actual_type = geometry.get("type")
    if actual_type in {"Point", "LineString"}:
        return actual_type
    return feature.geometry_type


# ===================================================
# CREATE FEATURE
# ===================================================
# `created_by` is passed in explicitly by the caller (derived from
# current_user['user_id'] in api/features.py, or threaded through
# from upload_service / geoclip_service) rather than read off the
# schema — see schemas/feature_schema.py for why FeatureCreate no
# longer carries this field.

def create_feature(feature, created_by: int | None = None):

    geometry_type = _resolved_geometry_type(feature)

    logger.info(
        f"Creating feature | geometry_type={geometry_type} | "
        f"case_id={feature.case_id} | layer_id={feature.layer_id} | created_by={created_by}"
    )

    # ---------------------------------
    # 1. CREATE CASE ONLY IF NOT PROVIDED
    # ---------------------------------
    case_id = feature.case_id or None

    if case_id is None:
        case_id = create_untitled_case(created_by)

    # ---------------------------------
    # 2. CREATE NEW LAYER ONLY IF NOT PROVIDED
    # ---------------------------------
    layer_id = feature.layer_id or None

    if layer_id is None:
        layer_id = _create_auto_layer(case_id)

    # ---------------------------------
    # 3. VALIDATE GEOMETRY INPUT BEFORE HITTING THE DB
    # ---------------------------------
    if feature.geometry_type == "Circle":
        if not feature.center or "lat" not in feature.center or "lng" not in feature.center:
            logger.warning(f"Feature creation rejected: Circle missing center | layer_id={layer_id}")
            raise UnprocessableEntityError("Circle features require a 'center' with lat/lng")
        if feature.radius is None:
            logger.warning(f"Feature creation rejected: Circle missing radius | layer_id={layer_id}")
            raise UnprocessableEntityError("Circle features require a 'radius'")
    else:
        if not feature.geometry:
            logger.warning(
                f"Feature creation rejected: missing geometry | "
                f"layer_id={layer_id} | geometry_type={feature.geometry_type}"
            )
            raise UnprocessableEntityError("'geometry' is required for this geometry_type")

    # ---------------------------------
    # 4. INSERT FEATURE
    # ---------------------------------
    try:
        with SessionLocal.begin() as db:

            if feature.geometry_type == "Circle":

                geometry = func.ST_Transform(
                    func.ST_Buffer(
                        func.ST_Transform(
                            func.ST_SetSRID(
                                func.ST_Point(feature.center["lng"], feature.center["lat"]), 4326
                            ),
                            3857,
                        ),
                        feature.radius,
                        256,
                    ),
                    4326,
                )
            else:
                geometry = func.ST_SetSRID(
                    func.ST_GeomFromGeoJSON(json.dumps(feature.geometry)), 4326
                )
            new_feature = Feature(
                layer_id=layer_id,
                case_id=case_id,
                name=feature.name,
                geom=geometry,
                geometry_type=geometry_type,
                radius=feature.radius if feature.geometry_type == "Circle" else None,
                properties=feature.properties,
                created_by=created_by,
            )
            db.add(new_feature)
            db.flush()
            feature_id = new_feature.id

    except IntegrityError as e:
        logger.error(f"Integrity error creating feature | layer_id={layer_id} | error={e}", exc_info=True)
        raise NotFoundError("The specified layer does not exist") from e

    except DataError as e:
        logger.error(f"Data error creating feature (bad geometry?) | layer_id={layer_id} | error={e}", exc_info=True)
        raise UnprocessableEntityError("Invalid geometry data") from e

    except SQLAlchemyError as e:
        logger.error(f"Unexpected DB error creating feature | layer_id={layer_id} | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to create feature") from e

    logger.info(f"Feature created | feature_id={feature_id} | case_id={case_id} | layer_id={layer_id}")

    return {
        "success": True,
        "feature_id": feature_id,
        "case_id": case_id,
        "layer_id": layer_id
    }


# ===================================================
# GET ALL FEATURES
# ===================================================

def get_features():

    logger.info("Fetching all features")

    try:
        with SessionLocal() as db:
            result = db.execute(_feature_select().order_by(Feature.id))
            rows = list(result)

    except SQLAlchemyError as e:
        logger.error(f"Failed to fetch features | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to fetch features") from e

    return [_row_to_feature_dict(row) for row in rows]


# ===================================================
# GET FEATURES OF A LAYER
# ===================================================
# FIX: previously ran the query with no check that layer_id exists.
# A nonexistent layer_id returned an empty list `[]` — indistinguishable
# from a real layer with zero features. Now verifies the layer exists
# first and raises NotFoundError (404) if not.

def get_layer_features(layer_id):

    logger.info(f"Fetching features for layer | layer_id={layer_id}")

    try:
        with SessionLocal() as db:
            layer_exists = db.scalar(select(Layer.id).where(Layer.id == layer_id))
            if layer_exists is None:
                logger.warning(f"Get layer features failed: layer not found | layer_id={layer_id}")
                raise NotFoundError("Layer not found")

            result = db.execute(
                _feature_select().where(Feature.layer_id == layer_id).order_by(Feature.id)
            )
            rows = list(result)

    except NotFoundError:
        raise

    except SQLAlchemyError as e:
        logger.error(f"Failed to fetch features for layer | layer_id={layer_id} | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to fetch features") from e

    return [_row_to_feature_dict(row) for row in rows]


# ===================================================
# GET SINGLE FEATURE
# ===================================================

def get_feature(feature_id):

    logger.info(f"Fetching feature | feature_id={feature_id}")

    try:
        with SessionLocal() as db:
            row = db.execute(
                _feature_select().where(Feature.id == feature_id)
            ).one_or_none()

    except SQLAlchemyError as e:
        logger.error(f"Failed to fetch feature | feature_id={feature_id} | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to fetch feature") from e

    if row is None:
        return None

    return _row_to_feature_dict(row)


# ===================================================
# UPDATE FEATURE
# ===================================================

def update_feature(feature_id, feature):

    logger.info(f"Updating feature | feature_id={feature_id}")

    try:
        with SessionLocal.begin() as db:
            existing = db.get(Feature, feature_id)
            if existing is None:
                logger.warning(f"Update feature failed: not found | feature_id={feature_id}")
                raise NotFoundError("Feature not found")
            existing.layer_id = feature.layer_id
            existing.name = feature.name
            existing.geom = func.ST_SetSRID(
                func.ST_GeomFromGeoJSON(json.dumps(feature.geometry)), 4326
            )
            existing.geometry_type = _resolved_geometry_type(feature)
            existing.properties = feature.properties
            existing.updated_at = datetime.now()

    except NotFoundError:
        raise

    except IntegrityError as e:
        logger.error(f"Integrity error updating feature | feature_id={feature_id} | error={e}", exc_info=True)
        raise NotFoundError("The specified layer does not exist") from e

    except DataError as e:
        logger.error(f"Data error updating feature (bad geometry?) | feature_id={feature_id} | error={e}", exc_info=True)
        raise UnprocessableEntityError("Invalid geometry data") from e

    except SQLAlchemyError as e:
        logger.error(f"Unexpected DB error updating feature | feature_id={feature_id} | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to update feature") from e

    logger.info(f"Feature updated | feature_id={feature_id}")

    return {
        "success": True,
        "message": "Feature updated successfully"
    }


# ===================================================
# PATCH FEATURE
# ===================================================

def patch_feature(feature_id, feature):

    logger.info(f"Patching feature | feature_id={feature_id}")

    try:
        with SessionLocal.begin() as db:
            existing = db.get(Feature, feature_id)
            if existing is None:
                logger.warning(f"Patch feature failed: not found | feature_id={feature_id}")
                raise NotFoundError("Feature not found")

            if feature.name is not None:
                existing.name = feature.name
            properties = dict(existing.properties or {})
            if feature.properties is not None:
                properties.update(feature.properties)
            existing.properties = properties
            existing.updated_at = datetime.now()

    except NotFoundError:
        raise

    except SQLAlchemyError as e:
        logger.error(f"Unexpected DB error patching feature | feature_id={feature_id} | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to update feature") from e

    logger.info(f"Feature patched | feature_id={feature_id}")

    return {
        "success": True,
        "message": "Feature updated successfully"
    }


# ===================================================
# DELETE FEATURE
# ===================================================

def delete_feature(feature_id):

    logger.warning(f"Deleting feature | feature_id={feature_id}")

    try:
        with SessionLocal.begin() as db:
            existing = db.get(Feature, feature_id)
            if existing is None:
                logger.warning(f"Delete feature failed: not found | feature_id={feature_id}")
                raise NotFoundError("Feature not found")
            db.delete(existing)

    except NotFoundError:
        raise

    except SQLAlchemyError as e:
        logger.error(f"Unexpected DB error deleting feature | feature_id={feature_id} | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to delete feature") from e

    logger.info(f"Feature deleted | feature_id={feature_id}")

    return {
        "success": True,
        "message": "Feature deleted successfully"
    }


# ===================================================
# IMPORT GEOJSON FEATURES
# ===================================================

def import_geojson_features(
    case_id: int,
    layer_id: int,
    geojson: dict,
    created_by: int = None
):

    logger.info(f"Importing GeoJSON features | case_id={case_id} | layer_id={layer_id}")

    imported = 0

    for item in geojson["features"]:

        geometry = item.get("geometry")

        if geometry is None:
            continue

        properties = item.get("properties", {})

        name = (
            properties.get("Name")
            or properties.get("name")
            or f"Imported Feature {imported + 1}"
        )

        feature = FeatureCreate(
            case_id=case_id,
            layer_id=layer_id,
            name=name,
            geometry=geometry,
            geometry_type=geometry["type"],
            properties=properties,
        )

        create_feature(feature, created_by)

        imported += 1

    logger.info(f"GeoJSON import complete | case_id={case_id} | layer_id={layer_id} | imported={imported}")

    return {
        "success": True,
        "imported_features": imported
    }

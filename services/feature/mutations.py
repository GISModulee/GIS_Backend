import json

from datetime import datetime

from geoalchemy2 import Geography, Geometry
from sqlalchemy import cast, exists, func, select
from sqlalchemy.exc import IntegrityError, DataError, SQLAlchemyError

from models.model import Comment, Feature, Layer, Case, Comment
from schemas.feature_schema import FeatureCreate
from utils.constants import (
    CASE_ID_REQUIRED,
    CASE_NOT_FOUND,
    FEATURE_CIRCLE_CENTER_REQUIRED,
    FEATURE_CIRCLE_RADIUS_REQUIRED,
    FEATURE_CREATE_CONSTRAINT_FAILED,
    FEATURE_CREATE_FAILED,
    FEATURE_DELETE_FAILED,
    FEATURE_FETCH_FAILED,
    FEATURE_GEOMETRY_REQUIRED,
    FEATURE_INVALID_GEOMETRY,
    FEATURE_LAYER_CASE_MISMATCH,
    FEATURE_LAYER_DOES_NOT_EXIST,
    FEATURE_NOT_FOUND,
    FEATURE_UPDATE_FAILED,
    FEATURES_FETCH_FAILED,
    LAYER_NOT_FOUND,
)
from utils.logger import logger
from utils.exceptions import (
    NotFoundError,
    BadRequestError,
    UnprocessableEntityError,
    ServiceUnavailableError,
)

from services.layer.layer_service import create_untitled_layer, get_layer
from services.feature.common import _resolved_geometry_type

# ===================================================
# UPDATE FEATURE
# ===================================================

async def update_feature(feature_id, feature, db):

    logger.info(f"Updating feature | feature_id={feature_id}")

    try:
        existing = db.get(Feature, feature_id)
        if existing is None:
            logger.warning(f"Update feature failed: not found | feature_id={feature_id}")
            raise NotFoundError(FEATURE_NOT_FOUND)
        existing.layer_id = feature.layer_id
        existing.name = feature.name
        existing.geom = func.ST_SetSRID(
            func.ST_GeomFromGeoJSON(json.dumps(feature.geometry)), 4326
        )
        existing.geometry_type = await _resolved_geometry_type(feature)
        existing.properties = feature.properties
        existing.updated_at = datetime.now()
        db.commit()

    except NotFoundError:
        raise

    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error updating feature | feature_id={feature_id} | error={e}", exc_info=True)
        raise NotFoundError(FEATURE_LAYER_DOES_NOT_EXIST) from e

    except DataError as e:
        db.rollback()
        logger.error(f"Data error updating feature (bad geometry?) | feature_id={feature_id} | error={e}", exc_info=True)
        raise UnprocessableEntityError(FEATURE_INVALID_GEOMETRY) from e

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Unexpected DB error updating feature | feature_id={feature_id} | error={e}", exc_info=True)
        raise ServiceUnavailableError(FEATURE_UPDATE_FAILED) from e

    logger.info(f"Feature updated | feature_id={feature_id}")

    return {
        "success": True,
        "message": "Feature updated successfully"
    }


# ===================================================
# PATCH FEATURE
# ===================================================

async def patch_feature(feature_id, feature, db):

    logger.info(f"Patching feature | feature_id={feature_id}")

    try:
        existing = db.get(Feature, feature_id)

        if existing is None:
            logger.warning(f"Patch feature failed: not found | feature_id={feature_id}")
            raise NotFoundError(FEATURE_NOT_FOUND)

        # ===================================================
        # MOVE FEATURE TO ANOTHER LAYER (OPTIONAL)
        # ===================================================
        if feature.layer_id is not None:

            destination_layer = db.get(Layer, feature.layer_id)

            if destination_layer is None:
                logger.warning(
                    f"Patch feature failed: destination layer not found | "
                    f"layer_id={feature.layer_id}"
                )
                raise NotFoundError(LAYER_NOT_FOUND)

            if destination_layer.case_id != existing.case_id:
                logger.warning(
                    f"Patch feature failed: destination layer belongs to different case | "
                    f"feature_id={feature_id} | "
                    f"feature_case={existing.case_id} | "
                    f"layer_case={destination_layer.case_id}"
                )
                raise BadRequestError(
                    "Destination layer does not belong to the same case"
                )

            existing.layer_id = feature.layer_id

        # ===================================================
        # RENAME FEATURE (OPTIONAL)
        # ===================================================
        if feature.name is not None:
            existing.name = feature.name

        # ===================================================
        # UPDATE FEATURE PROPERTIES (OPTIONAL)
        # ===================================================
        properties = dict(existing.properties or {})

        if feature.properties is not None:
            properties.update(feature.properties)

        existing.properties = properties

        existing.updated_at = datetime.now()

        db.commit()

    except NotFoundError:
        raise

    except BadRequestError:
        raise

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(
            f"Unexpected DB error patching feature | "
            f"feature_id={feature_id} | error={e}",
            exc_info=True
        )
        raise ServiceUnavailableError(FEATURE_UPDATE_FAILED) from e

    logger.info(f"Feature patched | feature_id={feature_id}")

    return {
        "success": True,
        "message": "Feature updated successfully"
    }


# ===================================================
# DELETE FEATURE
# ===================================================

async def delete_feature(feature_id, db):

    logger.warning(f"Deleting feature | feature_id={feature_id}")

    try:
        existing = db.get(Feature, feature_id)
        if existing is None:
            logger.warning(f"Delete feature failed: not found | feature_id={feature_id}")
            raise NotFoundError(FEATURE_NOT_FOUND)
        db.delete(existing)
        db.commit()

    except NotFoundError:
        raise

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Unexpected DB error deleting feature | feature_id={feature_id} | error={e}", exc_info=True)
        raise ServiceUnavailableError(FEATURE_DELETE_FAILED) from e

    logger.info(f"Feature deleted | feature_id={feature_id}")

    return {
        "success": True,
        "message": "Feature deleted successfully"
    }
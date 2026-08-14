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
from services.feature.common import _feature_select, _row_to_feature_dict, _row_to_feature_summary_dict

# ===================================================
# GET FEATURES OF A CASE
# ===================================================

async def get_case_features(case_id, db):

    logger.info(
        f"Fetching features for case | case_id={case_id}"
    )

    try:
        case_exists = db.scalar(
            select(Case.id).where(
                Case.id == case_id
            )
        )

        if case_exists is None:
            logger.warning(
                f"Get case features failed: case not found | case_id={case_id}"
            )
            raise NotFoundError(CASE_NOT_FOUND)

        result = db.execute(
            (await _feature_select())
            .where(
                Feature.case_id == case_id
            )
            .order_by(
                Feature.feature_number
            )
        )

        rows = list(result)

    except NotFoundError:
        raise

    except SQLAlchemyError as e:
        logger.error(
            f"Failed to fetch case features | case_id={case_id} | error={e}",
            exc_info=True
        )
        raise ServiceUnavailableError(
            FEATURES_FETCH_FAILED
        ) from e

    return [
        await _row_to_feature_dict(row)
        for row in rows
    ]

# ===================================================
# GET ALL FEATURES
# ===================================================

async def get_features(db):

    logger.info("Fetching all features")

    try:
        result = db.execute((await _feature_select()).order_by(Feature.id))
        rows = list(result)

    except SQLAlchemyError as e:
        logger.error(f"Failed to fetch features | error={e}", exc_info=True)
        raise ServiceUnavailableError(FEATURES_FETCH_FAILED) from e

    return [await _row_to_feature_dict(row) for row in rows]

# ===================================================
# GET SINGLE FEATURE BY NUMBER (scoped to case + layer)
# ===================================================

async def get_feature_by_number(case_id, layer_id, feature_number, db):

    logger.info(
        f"Fetching feature by number | case_id={case_id} | layer_id={layer_id} | feature_number={feature_number}"
    )

    try:
        row = db.execute(
            (await _feature_select()).where(
                Feature.case_id == case_id,
                Feature.layer_id == layer_id,
                Feature.feature_number == feature_number,
            )
        ).one_or_none()

    except SQLAlchemyError as e:
        logger.error(
            f"Failed to fetch feature by number | case_id={case_id} | layer_id={layer_id} | "
            f"feature_number={feature_number} | error={e}",
            exc_info=True
        )
        raise ServiceUnavailableError(FEATURE_FETCH_FAILED) from e

    if row is None:
        return None

    return await _row_to_feature_dict(row)

# ===================================================
# GET FEATURES OF A LAYER
# ===================================================
# FIX: previously ran the query with no check that layer_id exists.
# A nonexistent layer_id returned an empty list `[]` — indistinguishable
# from a real layer with zero features. Now verifies the layer exists
# first and raises NotFoundError (404) if not.
#
# UPDATED: now returns a minimal summary (id, feature_number, case_id,
# layer_id only) instead of the full feature dict — geometry and other
# metadata are intentionally omitted from this list view. Use
# get_feature_by_number() for full details on a single feature.

async def get_layer_features(layer_id, db):

    logger.info(f"Fetching features for layer | layer_id={layer_id}")

    try:
        layer_exists = db.scalar(select(Layer.id).where(Layer.id == layer_id))
        if layer_exists is None:
            logger.warning(f"Get layer features failed: layer not found | layer_id={layer_id}")
            raise NotFoundError(LAYER_NOT_FOUND)

        result = db.execute(
            (await _feature_select()).where(Feature.layer_id == layer_id).order_by(Feature.id)
        )
        rows = list(result)

    except NotFoundError:
        raise

    except SQLAlchemyError as e:
        logger.error(f"Failed to fetch features for layer | layer_id={layer_id} | error={e}", exc_info=True)
        raise ServiceUnavailableError(FEATURES_FETCH_FAILED) from e

    return [await _row_to_feature_summary_dict(row) for row in rows]


# ===================================================
# GET SINGLE FEATURE
# ===================================================

async def get_feature(feature_id, db):

    logger.info(f"Fetching feature | feature_id={feature_id}")

    try:
        row = db.execute(
            (await _feature_select()).where(Feature.id == feature_id)
        ).one_or_none()

    except SQLAlchemyError as e:
        logger.error(f"Failed to fetch feature | feature_id={feature_id} | error={e}", exc_info=True)
        raise ServiceUnavailableError(FEATURE_FETCH_FAILED) from e

    if row is None:
        return None

    return await _row_to_feature_dict(row)
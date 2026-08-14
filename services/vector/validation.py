import json

from geoalchemy2 import Geography, Geometry
from sqlalchemy import cast, func, select
from sqlalchemy.exc import DataError, IntegrityError, SQLAlchemyError
from sqlalchemy.orm import aliased

from models.model import Feature, Layer
from services.layer.layer_service import create_untitled_layer
from utils.constants import (
    FEATURE_INVALID_GEOMETRY,
    FEATURE_NUMBERS_NOT_FOUND_TEMPLATE,
    FEATURE_NUMBERS_VERIFY_FAILED,
    GEOMETRY_COMPUTE_UNAVAILABLE_TEMPLATE,
    LAYER_DUPLICATE_NAME_TEMPLATE,
    LAYER_DUPLICATE_SUFFIX_DEFAULT,
    VECTOR_BINARY_REQUIRES_TWO_TEMPLATE,
    VECTOR_BUFFER_FAILED,
    VECTOR_CENTROID_FAILED,
    VECTOR_COMPUTE_FAILURE_PREFIX,
    VECTOR_CONVEX_HULL_FAILED,
    VECTOR_CONVEX_HULL_REQUIRES_TWO,
    VECTOR_FEATURE_INVALID_GEOMETRY_TEMPLATE,
    VECTOR_OPERATION_FAILED_TEMPLATE,
    VECTOR_RESULT_SAVE_FAILED,
    VECTOR_UNION_FAILED,
    VECTOR_UNION_REQUIRES_TWO,
)
from utils.logger import logger
from utils.exceptions import (
    BadRequestError,
    ConflictError,
    NotFoundError,
    UnprocessableEntityError,
    ServiceUnavailableError,
)


# ===================================================
# VERIFY FEATURE NUMBERS
# ===================================================

async def _ensure_features_exist(case_id, feature_numbers, db):

    numbers = list(dict.fromkeys(feature_numbers))

    try:
        found = set(
            db.scalars(
                select(Feature.feature_number)
                .where(
                    Feature.case_id == case_id,
                    Feature.feature_number.in_(numbers)
                )
            ).all()
        )

    except SQLAlchemyError as e:
        logger.error(
            f"Failed to verify feature numbers | feature_numbers={numbers} | error={e}",
            exc_info=True
        )
        raise ServiceUnavailableError(
            FEATURE_NUMBERS_VERIFY_FAILED
        ) from e

    missing = [
        number
        for number in numbers
        if number not in found
    ]

    if missing:
        logger.warning(
            f"Vector operation rejected | missing feature numbers={missing}"
        )

        raise NotFoundError(
            FEATURE_NUMBERS_NOT_FOUND_TEMPLATE.format(missing=missing)
        )

    try:
        invalid_rows = db.execute(
            select(Feature.feature_number, Feature.name)
            .where(
                Feature.case_id == case_id,
                Feature.feature_number.in_(numbers),
                ~func.ST_IsValid(Feature.geom)
            )
            .order_by(Feature.feature_number)
        ).all()

    except SQLAlchemyError as e:
        logger.error(
            f"Failed to validate feature geometries | feature_numbers={numbers} | error={e}",
            exc_info=True
        )
        raise ServiceUnavailableError(
            FEATURE_NUMBERS_VERIFY_FAILED
        ) from e

    if invalid_rows:
        invalid = invalid_rows[0]
        feature_name = invalid.name or invalid.feature_number
        raise UnprocessableEntityError(
            VECTOR_FEATURE_INVALID_GEOMETRY_TEMPLATE.format(feature_name=feature_name)
        )

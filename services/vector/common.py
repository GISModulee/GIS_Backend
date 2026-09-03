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


async def _run_geometry(statement, error_message, db):
    try:
        geometry = db.scalar(statement)

    except DataError as e:
        raise UnprocessableEntityError(FEATURE_INVALID_GEOMETRY) from e

    except SQLAlchemyError as e:
        logger.error(
            f"Spatial operation failed | error={e}",
            exc_info=True
        )
        raise ServiceUnavailableError(error_message) from e

    if geometry is None:
        if error_message == VECTOR_OPERATION_FAILED_TEMPLATE.format(operation="intersection"):
            raise UnprocessableEntityError("The selected shapes are not intersecting")
        operation_name = error_message.replace(VECTOR_COMPUTE_FAILURE_PREFIX, "").capitalize()
        raise UnprocessableEntityError(
            GEOMETRY_COMPUTE_UNAVAILABLE_TEMPLATE.format(operation=operation_name)
        )

    return geometry

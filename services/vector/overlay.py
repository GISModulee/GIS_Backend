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

from services.vector.common import _run_geometry
from services.vector.validation import _ensure_features_exist
from services.vector.persistence import _save_vector_result

# ===================================================
# UNION
# ===================================================

async def union_features(case_id, feature_numbers, db, created_by=None, layer_name=None):

    if len(feature_numbers) < 2:
        raise BadRequestError(
            VECTOR_UNION_REQUIRES_TWO
        )

    await _ensure_features_exist(case_id, feature_numbers, db)

    geometry = await _run_geometry(
        select(
            func.ST_AsGeoJSON(
                func.ST_Union(
                    Feature.geom
                )
            )
        ).where(
            Feature.case_id == case_id,
            Feature.feature_number.in_(feature_numbers)
        ),
        VECTOR_UNION_FAILED,
        db,
    )

    saved = await _save_vector_result(case_id, "union", geometry, db, created_by, layer_name)

    return {
        "success": True,
        "operation": "union",
        "geometry": geometry,
        **saved,
    }


# ===================================================
# BINARY OPERATIONS
# ===================================================

async def _binary_operation(
    case_id,
    feature_numbers,
    operation,
    label,
    db,
    created_by=None,
    layer_name=None,
):

    if len(feature_numbers) != 2:
        raise BadRequestError(
            VECTOR_BINARY_REQUIRES_TWO_TEMPLATE.format(label=label)
        )

    await _ensure_features_exist(case_id, feature_numbers, db)

    left = aliased(Feature)
    right = aliased(Feature)

    geometry = await _run_geometry(
        select(
            func.ST_AsGeoJSON(
                operation(
                    left.geom,
                    right.geom
                )
            )
        ).where(
            left.case_id == case_id,
            right.case_id == case_id,
            left.feature_number == feature_numbers[0],
            right.feature_number == feature_numbers[1],
        ),
        VECTOR_OPERATION_FAILED_TEMPLATE.format(operation=label),
        db,
    )

    saved = await _save_vector_result(case_id, label, geometry, db, created_by, layer_name)

    return {
        "success": True,
        "operation": label,
        "geometry": geometry,
        **saved,
    }

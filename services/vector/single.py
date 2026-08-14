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
# BUFFER
# ===================================================

async def buffer_feature(case_id, feature_number, distance, db, created_by=None, layer_name=None):

    await _ensure_features_exist(case_id, [feature_number], db)

    buffered = cast(
        func.ST_Buffer(
            cast(
                Feature.geom,
                Geography
            ),
            distance,
            256
        ),
        Geometry(
            geometry_type="GEOMETRY",
            srid=4326
        ),
    )

    geometry = await _run_geometry(
        select(
            func.ST_AsGeoJSON(buffered)
        ).where(
            Feature.case_id == case_id,
            Feature.feature_number == feature_number
        ),
        VECTOR_BUFFER_FAILED,
        db,
    )

    saved = await _save_vector_result(case_id, "buffer", geometry, db, created_by, layer_name)

    return {
        "success": True,
        "operation": "buffer",
        "geometry": geometry,
        **saved,
    }


# ===================================================
# CENTROID
# ===================================================

async def centroid_feature(case_id, feature_number, db, created_by=None, layer_name=None):

    await _ensure_features_exist(case_id, [feature_number], db)

    geometry = await _run_geometry(
        select(
            func.ST_AsGeoJSON(
                func.ST_Centroid(
                    Feature.geom
                )
            )
        ).where(
            Feature.case_id == case_id,
            Feature.feature_number == feature_number
        ),
        VECTOR_CENTROID_FAILED,
        db,
    )

    saved = await _save_vector_result(case_id, "centroid", geometry, db, created_by, layer_name)

    return {
        "success": True,
        "operation": "centroid",
        "geometry": geometry,
        **saved,
    }


# ===================================================
# CONVEX HULL
# ===================================================

async def convex_hull(case_id, feature_numbers, db, created_by=None, layer_name=None):

    if len(feature_numbers) < 2:
        raise BadRequestError(
            VECTOR_CONVEX_HULL_REQUIRES_TWO
        )

    await _ensure_features_exist(case_id, feature_numbers, db)

    geometry = await _run_geometry(
        select(
            func.ST_AsGeoJSON(
                func.ST_ConvexHull(
                    func.ST_Collect(
                        Feature.geom
                    )
                )
            )
        ).where(
            Feature.case_id == case_id,
            Feature.feature_number.in_(feature_numbers)
        ),
        VECTOR_CONVEX_HULL_FAILED,
        db,
    )

    saved = await _save_vector_result(case_id, "convex_hull", geometry, db, created_by, layer_name)

    return {
        "success": True,
        "operation": "convex_hull",
        "geometry": geometry,
        **saved,
    }

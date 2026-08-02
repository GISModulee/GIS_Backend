from geoalchemy2 import Geography, Geometry
from sqlalchemy import cast, func, select
from sqlalchemy.exc import DataError, SQLAlchemyError
from sqlalchemy.orm import aliased
 
from models.model import Feature
from utils.constants import (
    FEATURE_INVALID_GEOMETRY,
    FEATURE_NUMBERS_NOT_FOUND_TEMPLATE,
    FEATURE_NUMBERS_VERIFY_FAILED,
    GEOMETRY_COMPUTE_UNAVAILABLE_TEMPLATE,
    VECTOR_BINARY_REQUIRES_TWO_TEMPLATE,
    VECTOR_BUFFER_FAILED,
    VECTOR_CENTROID_FAILED,
    VECTOR_COMPUTE_FAILURE_PREFIX,
    VECTOR_CONVEX_HULL_FAILED,
    VECTOR_CONVEX_HULL_REQUIRES_TWO,
    VECTOR_OPERATION_FAILED_TEMPLATE,
    VECTOR_UNION_FAILED,
    VECTOR_UNION_REQUIRES_TWO,
)
from utils.logger import logger
from utils.exceptions import (
    BadRequestError,
    NotFoundError,
    UnprocessableEntityError,
    ServiceUnavailableError,
)
 
 
def _run_geometry(statement, error_message, db):
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
        operation_name = error_message.replace(VECTOR_COMPUTE_FAILURE_PREFIX, "").capitalize()
        raise UnprocessableEntityError(
            GEOMETRY_COMPUTE_UNAVAILABLE_TEMPLATE.format(operation=operation_name)
        )
 
    return geometry
 
 
# ===================================================
# VERIFY FEATURE NUMBERS
# ===================================================
 
def _ensure_features_exist(case_id, feature_numbers, db):
 
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
 
 
# ===================================================
# UNION
# ===================================================
 
def union_features(case_id, feature_numbers, db):
 
    if len(feature_numbers) < 2:
        raise BadRequestError(
            VECTOR_UNION_REQUIRES_TWO
        )
 
    _ensure_features_exist(case_id, feature_numbers, db)
 
    geometry = _run_geometry(
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
 
    return {
        "success": True,
        "operation": "union",
        "geometry": geometry
    }
 
 
# ===================================================
# BINARY OPERATIONS
# ===================================================
 
def _binary_operation(
    case_id,
    feature_numbers,
    operation,
    label,
    db
):
 
    if len(feature_numbers) != 2:
        raise BadRequestError(
            VECTOR_BINARY_REQUIRES_TWO_TEMPLATE.format(label=label)
        )
 
    _ensure_features_exist(case_id, feature_numbers, db)
 
    left = aliased(Feature)
    right = aliased(Feature)
 
    geometry = _run_geometry(
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
 
    return {
        "success": True,
        "operation": label,
        "geometry": geometry
    }
 
 
def intersection_features(case_id, feature_numbers, db):
    return _binary_operation(
        case_id,
        feature_numbers,
        func.ST_Intersection,
        "intersection",
        db
    )
 
 
def difference_features(case_id, feature_numbers, db):
    return _binary_operation(
        case_id,
        feature_numbers,
        func.ST_Difference,
        "difference",
        db
    )
 
 
def symdifference_features(case_id, feature_numbers, db):
    return _binary_operation(
        case_id,
        feature_numbers,
        func.ST_SymDifference,
        "symdifference",
        db
    )
 
 
# ===================================================
# BUFFER
# ===================================================
 
def buffer_feature(case_id, feature_number, distance, db):
 
    _ensure_features_exist(case_id, [feature_number], db)
 
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
 
    geometry = _run_geometry(
        select(
            func.ST_AsGeoJSON(buffered)
        ).where(
            Feature.case_id == case_id,
            Feature.feature_number == feature_number
        ),
        VECTOR_BUFFER_FAILED,
        db,
    )
 
    return {
        "success": True,
        "operation": "buffer",
        "geometry": geometry
    }
 
 
# ===================================================
# CENTROID
# ===================================================
 
def centroid_feature(case_id, feature_number, db):
 
    _ensure_features_exist(case_id, [feature_number], db)
 
    geometry = _run_geometry(
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
 
    return {
        "success": True,
        "operation": "centroid",
        "geometry": geometry
    }
 
 
# ===================================================
# CONVEX HULL
# ===================================================
 
def convex_hull(case_id, feature_numbers, db):
 
    if len(feature_numbers) < 2:
        raise BadRequestError(
            VECTOR_CONVEX_HULL_REQUIRES_TWO
        )
 
    _ensure_features_exist(case_id, feature_numbers, db)
 
    geometry = _run_geometry(
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
 
    return {
        "success": True,
        "operation": "convex_hull",
        "geometry": geometry
    }

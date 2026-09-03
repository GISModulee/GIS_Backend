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
from services.vector.overlay import _binary_operation

async def _iterative_operation(
    case_id,
    feature_numbers,
    operation,
    label,
    db,
    created_by=None,
    layer_name=None,
):
    await _ensure_features_exist(case_id, feature_numbers, db)

    geometries = []

    for feature_number in feature_numbers:
        geom = db.scalar(
            select(Feature.geom).where(
                Feature.case_id == case_id,
                Feature.feature_number == feature_number,
            )
        )
        geometries.append(geom)

    result_geom = geometries[0]

    for geom in geometries[1:]:
        if label == "intersection" and not db.scalar(
            select(func.ST_Intersects(result_geom, geom))
        ):
            result_geom = None
            break

        result_geom = db.scalar(
            select(operation(result_geom, geom))
        )

        if result_geom is None:
            break

    geometry = await _run_geometry(
        select(func.ST_AsGeoJSON(result_geom)),
        VECTOR_OPERATION_FAILED_TEMPLATE.format(operation=label),
        db,
    )

    saved = await _save_vector_result(
        case_id,
        label,
        geometry,
        db,
        created_by,
        layer_name,
    )

    return {
        "success": True,
        "operation": label,
        "geometry": geometry,
        **saved,
    }


async def intersection_features(
    case_id,
    feature_numbers,
    db,
    created_by=None,
    layer_name=None,
):
    if len(feature_numbers) < 2:
        raise BadRequestError(
            VECTOR_BINARY_REQUIRES_TWO_TEMPLATE.format(label="intersection")
        )

    # Preserve existing behavior
    if len(feature_numbers) == 2:
        return await _binary_operation(
            case_id,
            feature_numbers,
            func.ST_Intersection,
            "intersection",
            db,
            created_by,
            layer_name,
        )

    return await _iterative_operation(
        case_id,
        feature_numbers,
        func.ST_Intersection,
        "intersection",
        db,
        created_by,
        layer_name,
    )


async def difference_features(case_id, feature_numbers, db, created_by=None, layer_name=None):
    return await _binary_operation(
        case_id,
        feature_numbers,
        func.ST_Difference,
        "difference",
        db,
        created_by,
        layer_name,
    )


async def symdifference_features(case_id, feature_numbers, db, created_by=None, layer_name=None):
    return await _binary_operation(
        case_id,
        feature_numbers,
        func.ST_SymDifference,
        "symdifference",
        db,
        created_by,
        layer_name,
    )

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
        operation_name = error_message.replace(VECTOR_COMPUTE_FAILURE_PREFIX, "").capitalize()
        raise UnprocessableEntityError(
            GEOMETRY_COMPUTE_UNAVAILABLE_TEMPLATE.format(operation=operation_name)
        )

    return geometry


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

# ===================================================
# SAVE VECTOR OPERATION RESULT AS A FEATURE
# ===================================================
# Single source of truth for turning a computed geometry into a saved
# Feature. Creates the "Vector Layer N" (layer_type="vector") and
# inserts the resulting Feature in the SAME transaction, using the
# SAME layer_id returned by the layer creation — there is no seam
# where the two could drift apart, unlike having the layer created in
# one place and the feature saved somewhere else.

async def _save_vector_result(
    case_id,
    operation_label,
    geometry_geojson,
    db,
    created_by=None,
    layer_name=None,
):

    try:
        # Lock the case for both layer numbering and feature numbering,
        # matching the pattern used in feature_service.create_feature.
        db.execute(
            select(func.pg_advisory_xact_lock(case_id))
        )

        resolved_layer_name = layer_name.strip() if layer_name else None

        if resolved_layer_name:
            existing_layer_id = db.scalar(
                select(Layer.id).where(
                    Layer.case_id == case_id,
                    Layer.name == resolved_layer_name,
                ).limit(1)
            )

            if existing_layer_id is not None:
                raise ConflictError(
                    LAYER_DUPLICATE_NAME_TEMPLATE.format(
                        name=resolved_layer_name,
                        suffix=LAYER_DUPLICATE_SUFFIX_DEFAULT,
                    )
                )

            layer = Layer(
                case_id=case_id,
                name=resolved_layer_name,
                layer_type="vector",
                visible=True,
            )
            db.add(layer)
            db.flush()
            layer_id = layer.id
        else:
            layer_id = await create_untitled_layer(case_id, db, layer_type="vector")
            resolved_layer_name = db.scalar(
                select(Layer.name).where(Layer.id == layer_id)
            )

        max_feature_number = db.scalar(
            select(
                func.coalesce(func.max(Feature.feature_number), 0)
            ).where(
                Feature.case_id == case_id
            )
        )
        next_feature_number = max_feature_number + 1

        parsed_geometry = json.loads(geometry_geojson)
        geometry_type = parsed_geometry.get("type")

        geom = func.ST_SetSRID(
            func.ST_GeomFromGeoJSON(geometry_geojson),
            4326
        )

        new_feature = Feature(
            feature_number=next_feature_number,
            layer_id=layer_id,
            case_id=case_id,
            name=f"{operation_label.capitalize()} Result",
            geom=geom,
            geometry_type=geometry_type,
            properties={"operation": operation_label},
            created_by=created_by,
        )

        db.add(new_feature)
        db.commit()
        db.refresh(new_feature)

        return {
            "feature_id": new_feature.id,
            "feature_number": next_feature_number,
            "layer_id": layer_id,
            "layer_name": resolved_layer_name,
        }

    except ConflictError:
        db.rollback()
        raise

    except (DataError, IntegrityError) as e:
        db.rollback()
        logger.error(
            f"Failed to save vector result (bad geometry?) | case_id={case_id} | "
            f"operation={operation_label} | error={e}",
            exc_info=True
        )
        raise UnprocessableEntityError(FEATURE_INVALID_GEOMETRY) from e

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(
            f"Failed to save vector result | case_id={case_id} | operation={operation_label} | error={e}",
            exc_info=True
        )
        raise ServiceUnavailableError(VECTOR_RESULT_SAVE_FAILED) from e


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


async def intersection_features(case_id, feature_numbers, db, created_by=None, layer_name=None):
    return await _binary_operation(
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

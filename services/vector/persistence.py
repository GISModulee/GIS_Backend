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

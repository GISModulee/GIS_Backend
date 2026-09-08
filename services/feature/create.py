import json

from datetime import datetime

from geoalchemy2 import Geography, Geometry
from sqlalchemy import cast, exists, func, select
from sqlalchemy.exc import IntegrityError, DataError, SQLAlchemyError

from models.model import Comment, Feature, Layer
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
from services.feature.common import _create_auto_layer, _resolved_geometry_type

# ===================================================
# CREATE FEATURE
# ===================================================
# `created_by` is passed in explicitly by the caller (derived from
# current_user['user_id'] in api/features.py, or threaded through
# from upload_service / geoclip_service) rather than read off the
# schema — see schemas/feature_schema.py for why FeatureCreate no
# longer carries this field.

async def create_feature(feature, db, created_by: int | None = None):

    geometry_type = await _resolved_geometry_type(feature)

    logger.info(
        f"Creating feature | geometry_type={geometry_type} | "
        f"case_id={feature.case_id} | layer_id={feature.layer_id} | created_by={created_by}"
    )

# ---------------------------------
# 1. CASE ID IS MANDATORY
# ---------------------------------
    case_id = feature.case_id

    if case_id is None:
        raise BadRequestError(CASE_ID_REQUIRED)

    # ---------------------------------
    # 2. CREATE NEW LAYER ONLY IF NOT PROVIDED
    # ---------------------------------
    layer_id = feature.layer_id or None

    if layer_id is None:
        layer_id = await _create_auto_layer(case_id, db)

    # ---------------------------------
    # 3. VALIDATE GEOMETRY INPUT BEFORE HITTING THE DB
    # ---------------------------------
    if feature.geometry_type == "Circle":
        if not feature.center or "lat" not in feature.center or "lng" not in feature.center:
            logger.warning(f"Feature creation rejected: Circle missing center | layer_id={layer_id}")
            raise UnprocessableEntityError(FEATURE_CIRCLE_CENTER_REQUIRED)
        if feature.radius is None:
            logger.warning(f"Feature creation rejected: Circle missing radius | layer_id={layer_id}")
            raise UnprocessableEntityError(FEATURE_CIRCLE_RADIUS_REQUIRED)
    else:
        if not feature.geometry:
            logger.warning(
                f"Feature creation rejected: missing geometry | "
                f"layer_id={layer_id} | geometry_type={feature.geometry_type}"
            )
            raise UnprocessableEntityError(FEATURE_GEOMETRY_REQUIRED)

# ---------------------------------
# 4. INSERT FEATURE
# ---------------------------------
    try:
        # Lock the case while generating feature numbers
        db.execute(
            select(func.pg_advisory_xact_lock(case_id))
        )

        # Check layer exists
        layer = db.get(Layer, layer_id)

        if layer is None:
            raise NotFoundError(LAYER_NOT_FOUND)

        # Ensure the layer belongs to the given case
        if layer.case_id != case_id:
            raise BadRequestError(
                FEATURE_LAYER_CASE_MISMATCH
            )

        # Generate next feature number for this case
        max_feature_number = db.scalar(
            select(
                func.coalesce(func.max(Feature.feature_number), 0)
            ).where(
                Feature.case_id == case_id
            )
        )

        next_feature_number = max_feature_number + 1

        if feature.geometry_type == "Circle":

            geometry = cast(
                func.ST_Buffer(
                    cast(
                        func.ST_SetSRID(
                            func.ST_Point(
                                feature.center["lng"],
                                feature.center["lat"]
                            ),
                            4326,
                        ),
                        Geography,
                    ),
                    feature.radius,
                    256,
                ),
                Geometry(geometry_type="GEOMETRY", srid=4326),
            )

        else:
            geometry = func.ST_SetSRID(
                func.ST_GeomFromGeoJSON(
                    json.dumps(feature.geometry)
                ),
                4326
            )

        new_feature = Feature(
            feature_number=next_feature_number,
            layer_id=layer_id,
            case_id=case_id,
            name=feature.name,
            geom=geometry,
            geometry_type=geometry_type,
            radius=feature.radius if feature.geometry_type == "Circle" else None,
            properties=feature.properties,
            created_by=created_by,
        )

        db.add(new_feature)
        db.commit()
        db.refresh(new_feature)

        feature_id = new_feature.id

    except IntegrityError as e:
        db.rollback()
        logger.error(
            f"Integrity error creating feature | layer_id={layer_id} | error={e}",
            exc_info=True
        )
        raise BadRequestError(
    FEATURE_CREATE_CONSTRAINT_FAILED
        ) from e

    except DataError as e:
        db.rollback()
        logger.error(
            f"Data error creating feature (bad geometry?) | layer_id={layer_id} | error={e}",
            exc_info=True
        )
        raise UnprocessableEntityError(FEATURE_INVALID_GEOMETRY) from e

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(
            f"Unexpected DB error creating feature | layer_id={layer_id} | error={e}",
            exc_info=True
        )
        raise ServiceUnavailableError(FEATURE_CREATE_FAILED) from e

    logger.info(
        f"Feature created | feature_id={feature_id} | case_id={case_id} | layer_id={layer_id}"
    )

    return {
        "success": True,
        "feature_id": feature_id,
        "feature_number": next_feature_number,
        "case_id": case_id,
        "layer_id": layer_id
    }
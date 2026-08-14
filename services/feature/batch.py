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

# ===================================================
# BATCH CREATE FEATURES (for bulk uploads — KML/GeoJSON imports)
# ===================================================
# Unlike create_feature() (one feature, one commit, used by the
# single-feature POST /features route), this handles many features
# in ONE transaction: one lock, one feature_number lookup, one
# commit. Built for upload_service.py's KML/GeoJSON extractors.

def create_features_batch(features: list, case_id: int, layer_id: int, db, created_by: int | None = None):
    """
    features: list of dicts, each with keys:
        name, geometry (GeoJSON dict), geometry_type, properties
    Circles aren't supported in this batch path (uploads don't produce
    them) — only Polygon/LineString/Point geometries from parsed files.
    """

    logger.info(
        f"Batch creating {len(features)} features | case_id={case_id} | layer_id={layer_id}"
    )

    if not features:
        return []

    try:
        # Lock ONCE for the whole batch, not per-feature
        db.execute(select(func.pg_advisory_xact_lock(case_id)))

        layer = db.get(Layer, layer_id)
        if layer is None:
            raise NotFoundError(LAYER_NOT_FOUND)
        if layer.case_id != case_id:
            raise BadRequestError(FEATURE_LAYER_CASE_MISMATCH)

        # ONE lookup for the starting number, then count up in Python
        max_feature_number = db.scalar(
            select(func.coalesce(func.max(Feature.feature_number), 0))
            .where(Feature.case_id == case_id)
        )

        new_features = []
        next_number = max_feature_number + 1

        for f in features:
            if not f.get("geometry"):
                continue

            geometry = func.ST_SetSRID(
                func.ST_GeomFromGeoJSON(json.dumps(f["geometry"])),
                4326
            )

            new_feature = Feature(
                feature_number=next_number,
                layer_id=layer_id,
                case_id=case_id,
                name=f.get("name"),
                geom=geometry,
                geometry_type=f.get("geometry_type", "Polygon"),
                properties=f.get("properties", {}),
                created_by=created_by,
            )
            new_features.append(new_feature)
            next_number += 1

        # ONE bulk add, ONE commit — not one per feature
        db.add_all(new_features)
        db.commit()

        for f in new_features:
            db.refresh(f)

    except (NotFoundError, BadRequestError):
        db.rollback()
        raise

    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error batch creating features | layer_id={layer_id} | error={e}", exc_info=True)
        raise BadRequestError(FEATURE_CREATE_CONSTRAINT_FAILED) from e

    except DataError as e:
        db.rollback()
        logger.error(f"Data error batch creating features | layer_id={layer_id} | error={e}", exc_info=True)
        raise UnprocessableEntityError(FEATURE_INVALID_GEOMETRY) from e

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Unexpected DB error batch creating features | layer_id={layer_id} | error={e}", exc_info=True)
        raise ServiceUnavailableError(FEATURE_CREATE_FAILED) from e

    logger.info(f"Batch created {len(new_features)} features | case_id={case_id} | layer_id={layer_id}")

    return [
        {"feature_id": f.id, "feature_number": f.feature_number}
        for f in new_features
    ]
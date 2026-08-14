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
# HELPERS
# ===================================================

async def _create_auto_layer(case_id: int, db):
    return await create_untitled_layer(case_id, db)


async def _row_to_feature_dict(row):
    try:
        geometry = json.loads(row.geometry) if row.geometry else None
    except (TypeError, ValueError) as e:
        logger.error(
            f"Malformed geometry JSON for feature_id={row.id} | error={e}"
        )
        geometry = None

    geometry_type = row.geometry_type

    if geometry and geometry.get("type") in {"Point", "LineString"}:
        geometry_type = geometry["type"]

    return {
        "id": row.id,
        "feature_number": row.feature_number,
        "case_id": row.case_id,
        "layer_id": row.layer_id,
        "name": row.name,
        "geometry_type": geometry_type,
        "radius": row.radius,
        "geometry": geometry,
        "properties": row.properties,
        "created_by": row.created_by,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "has_comments": row.has_comments,
    }

async def _row_to_feature_summary_dict(row):
    """Minimal feature representation for list views — only IDs, no geometry or metadata."""
    return {
        "id": row.id,
        "feature_number": row.feature_number,
        "case_id": row.case_id,
        "layer_id": row.layer_id,
        "has_comments": bool(row.has_comments),
    }


async def _feature_select():

    has_comments = (
        select(Comment.id)
        .where(
            Comment.case_id == Feature.case_id,
            Comment.layer_id == Feature.layer_id,
            Comment.feature_number == Feature.feature_number,
        )
        .correlate(Feature)
        .exists()
    )

    return select(
        Feature.id,
        Feature.feature_number,
        Feature.case_id,
        Feature.layer_id,
        Feature.name,
        Feature.geometry_type,
        Feature.radius,
        func.ST_AsGeoJSON(Feature.geom).label("geometry"),
        Feature.properties,
        Feature.created_by,
        Feature.created_at,
        Feature.updated_at,
        has_comments.label("has_comments"),
    )


async def _resolved_geometry_type(feature):
    """Use the actual GeoJSON type for points and lines only."""
    if feature.geometry_type == "Circle":
        return "Circle"
    geometry = feature.geometry or {}
    actual_type = geometry.get("type")
    if actual_type in {"Point", "LineString"}:
        return actual_type
    return feature.geometry_type
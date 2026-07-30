from geoalchemy2 import Geography, Geometry
from sqlalchemy import cast, func, select
from sqlalchemy.exc import DataError, SQLAlchemyError
from sqlalchemy.orm import Session, aliased

from database.database import SessionLocal
from models.model import Feature
from utils.logger import logger
from utils.exceptions import BadRequestError, NotFoundError, UnprocessableEntityError, ServiceUnavailableError


def _run_geometry(statement, error_message):
    try:
        with SessionLocal() as db:
            geometry = db.scalar(statement)
    except DataError as e:
        raise UnprocessableEntityError("Invalid geometry data") from e
    except SQLAlchemyError as e:
        logger.error(f"Spatial operation failed | error={e}", exc_info=True)
        raise ServiceUnavailableError(error_message) from e
    if geometry is None:
        raise UnprocessableEntityError(error_message.replace("Failed to compute ", "").capitalize() + " could not be computed")
    return geometry


def _ensure_features_exist(feature_ids):
    ids = list(dict.fromkeys(feature_ids))  # de-dupe, preserve order
    try:
        with SessionLocal() as db:
            found = set(db.scalars(select(Feature.id).where(Feature.id.in_(ids))).all())
    except SQLAlchemyError as e:
        logger.error(f"Failed to verify feature existence | feature_ids={ids} | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to verify features") from e

    missing = [feature_id for feature_id in ids if feature_id not in found]
    if missing:
        logger.warning(f"Vector operation rejected: feature(s) not found | missing={missing}")
        raise NotFoundError(
            f"Feature(s) not found: {missing}" if len(missing) > 1 else f"Feature {missing[0]} not found"
        )


def union_features(feature_ids):
    if len(feature_ids) < 2:
        raise BadRequestError("At least two features are required for union")
    _ensure_features_exist(feature_ids)
    geometry = _run_geometry(
        select(func.ST_AsGeoJSON(func.ST_Union(Feature.geom))).where(Feature.id.in_(feature_ids)),
        "Failed to compute union",
    )
    return {"success": True, "operation": "union", "geometry": geometry}


def _binary_operation(feature_ids, operation, label):
    if len(feature_ids) != 2:
        raise BadRequestError(f"{label} requires exactly two features")
    _ensure_features_exist(feature_ids)
    left, right = aliased(Feature), aliased(Feature)
    geometry = _run_geometry(
        select(func.ST_AsGeoJSON(operation(left.geom, right.geom))).where(
            left.id == feature_ids[0], right.id == feature_ids[1]
        ),
        f"Failed to compute {label.lower()}",
    )
    return {"success": True, "operation": label.lower().replace(" ", ""), "geometry": geometry}


def intersection_features(feature_ids):
    return _binary_operation(feature_ids, func.ST_Intersection, "intersection")


def difference_features(feature_ids):
    return _binary_operation(feature_ids, func.ST_Difference, "difference")


def symdifference_features(feature_ids):
    return _binary_operation(feature_ids, func.ST_SymDifference, "symdifference")


def buffer_feature(feature_id, distance):
    _ensure_features_exist([feature_id])
    buffered = cast(
        func.ST_Buffer(cast(Feature.geom, Geography), distance, 256),
        Geometry(geometry_type="GEOMETRY", srid=4326),
    )
    geometry = _run_geometry(
        select(func.ST_AsGeoJSON(buffered)).where(Feature.id == feature_id),
        "Failed to compute buffer",
    )
    return {"success": True, "operation": "buffer", "geometry": geometry}


def centroid_feature(feature_id):
    _ensure_features_exist([feature_id])
    geometry = _run_geometry(
        select(func.ST_AsGeoJSON(func.ST_Centroid(Feature.geom))).where(Feature.id == feature_id),
        "Failed to compute centroid",
    )
    return {"success": True, "operation": "centroid", "geometry": geometry}


def convex_hull(feature_ids):
    if len(feature_ids) < 2:
        return {"success": False, "message": "At least two features are required for convex hull"}
    _ensure_features_exist(feature_ids)
    geometry = _run_geometry(
        select(func.ST_AsGeoJSON(func.ST_ConvexHull(func.ST_Collect(Feature.geom)))).where(
            Feature.id.in_(feature_ids)
        ),
        "Failed to compute convex hull",
    )
    return {"success": True, "operation": "convex_hull", "geometry": geometry}
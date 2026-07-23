from sqlalchemy import text, bindparam
from sqlalchemy.exc import DataError, SQLAlchemyError
 
from database.database import engine
from utils.logger import logger
from utils.exception_handler import (
    BadRequestError,
    UnprocessableEntityError,
    ServiceUnavailableError,
)
 
 
# ===================================================
# UNION FEATURES
# ===================================================
 
def union_features(feature_ids):
 
    logger.info(f"Union requested | feature_ids={feature_ids}")
 
    if len(feature_ids) < 2:
        logger.warning(f"Union rejected: fewer than 2 features | feature_ids={feature_ids}")
        raise BadRequestError("At least two features are required for union")
 
    try:
        with engine.connect() as conn:
 
            stmt = text("""
                SELECT ST_AsGeoJSON(
                    ST_Union(geom)
                ) AS geometry
                FROM features
                WHERE id IN :feature_ids
            """).bindparams(
                bindparam("feature_ids", expanding=True)
            )
 
            result = conn.execute(
                stmt,
                {
                    "feature_ids": feature_ids
                }
            )
 
            row = result.fetchone()
 
    except DataError as e:
        logger.error(f"Data error computing union | feature_ids={feature_ids} | error={e}", exc_info=True)
        raise UnprocessableEntityError("Invalid geometry data") from e
 
    except SQLAlchemyError as e:
        logger.error(f"Unexpected DB error computing union | feature_ids={feature_ids} | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to compute union") from e
 
    if row is None or row.geometry is None:
        logger.warning(f"Union could not be computed | feature_ids={feature_ids}")
        raise UnprocessableEntityError("Union could not be computed")
 
    logger.info(f"Union computed | feature_ids={feature_ids}")
 
    return {
        "success": True,
        "operation": "union",
        "geometry": row.geometry
    }
 
 
# ===================================================
# INTERSECTION FEATURES
# ===================================================
 
def intersection_features(feature_ids):
 
    logger.info(f"Intersection requested | feature_ids={feature_ids}")
 
    if len(feature_ids) != 2:
        logger.warning(f"Intersection rejected: requires exactly 2 features | feature_ids={feature_ids}")
        raise BadRequestError("Intersection requires exactly two features")
 
    try:
        with engine.connect() as conn:
 
            stmt = text("""
                SELECT ST_AsGeoJSON(
                    ST_Intersection(f1.geom, f2.geom)
                ) AS geometry
                FROM features f1
                JOIN features f2
                  ON f1.id != f2.id
                WHERE f1.id = :id1
                  AND f2.id = :id2
            """)
 
            result = conn.execute(
                stmt,
                {
                    "id1": feature_ids[0],
                    "id2": feature_ids[1]
                }
            )
 
            row = result.fetchone()
 
    except DataError as e:
        logger.error(f"Data error computing intersection | feature_ids={feature_ids} | error={e}", exc_info=True)
        raise UnprocessableEntityError("Invalid geometry data") from e
 
    except SQLAlchemyError as e:
        logger.error(f"Unexpected DB error computing intersection | feature_ids={feature_ids} | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to compute intersection") from e
 
    if row is None or row.geometry is None:
        logger.warning(f"Intersection could not be computed | feature_ids={feature_ids}")
        raise UnprocessableEntityError("Intersection could not be computed")
 
    logger.info(f"Intersection computed | feature_ids={feature_ids}")
 
    return {
        "success": True,
        "operation": "intersection",
        "geometry": row.geometry
    }
 
 
# ===================================================
# DIFFERENCE FEATURES
# ===================================================
 
def difference_features(feature_ids):
 
    logger.info(f"Difference requested | feature_ids={feature_ids}")
 
    if len(feature_ids) != 2:
        logger.warning(f"Difference rejected: requires exactly 2 features | feature_ids={feature_ids}")
        raise BadRequestError("Difference requires exactly two features")
 
    try:
        with engine.connect() as conn:
 
            result = conn.execute(
                text("""
                    SELECT ST_AsGeoJSON(
                        ST_Difference(f1.geom, f2.geom)
                    ) AS geometry
                    FROM features f1,
                         features f2
                    WHERE f1.id = :id1
                      AND f2.id = :id2
                """),
                {
                    "id1": feature_ids[0],
                    "id2": feature_ids[1]
                }
            )
 
            row = result.fetchone()
 
    except DataError as e:
        logger.error(f"Data error computing difference | feature_ids={feature_ids} | error={e}", exc_info=True)
        raise UnprocessableEntityError("Invalid geometry data") from e
 
    except SQLAlchemyError as e:
        logger.error(f"Unexpected DB error computing difference | feature_ids={feature_ids} | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to compute difference") from e
 
    if row is None or row.geometry is None:
        logger.warning(f"Difference could not be computed | feature_ids={feature_ids}")
        raise UnprocessableEntityError("Difference could not be computed")
 
    logger.info(f"Difference computed | feature_ids={feature_ids}")
 
    return {
        "success": True,
        "operation": "difference",
        "geometry": row.geometry
    }
 
 
# ===================================================
# SYMMETRIC DIFFERENCE FEATURES
# ===================================================
 
def symdifference_features(feature_ids):
 
    logger.info(f"Symmetric difference requested | feature_ids={feature_ids}")
 
    if len(feature_ids) != 2:
        logger.warning(f"Symmetric difference rejected: requires exactly 2 features | feature_ids={feature_ids}")
        raise BadRequestError("Symmetric Difference requires exactly two features")
 
    try:
        with engine.connect() as conn:
 
            result = conn.execute(
                text("""
                    SELECT ST_AsGeoJSON(
                        ST_SymDifference(f1.geom, f2.geom)
                    ) AS geometry
                    FROM features f1,
                         features f2
                    WHERE f1.id = :id1
                      AND f2.id = :id2
                """),
                {
                    "id1": feature_ids[0],
                    "id2": feature_ids[1]
                }
            )
 
            row = result.fetchone()
 
    except DataError as e:
        logger.error(f"Data error computing symmetric difference | feature_ids={feature_ids} | error={e}", exc_info=True)
        raise UnprocessableEntityError("Invalid geometry data") from e
 
    except SQLAlchemyError as e:
        logger.error(f"Unexpected DB error computing symmetric difference | feature_ids={feature_ids} | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to compute symmetric difference") from e
 
    if row is None or row.geometry is None:
        logger.warning(f"Symmetric difference could not be computed | feature_ids={feature_ids}")
        raise UnprocessableEntityError("Symmetric Difference could not be computed")
 
    logger.info(f"Symmetric difference computed | feature_ids={feature_ids}")
 
    return {
        "success": True,
        "operation": "symdifference",
        "geometry": row.geometry
    }
 
 
# ===================================================
# Buffer FEATURE
# ===================================================
 
def buffer_feature(feature_id, distance):
 
    conn = engine.connect()
 
    try:
 
        result = conn.execute(
            text("""
                SELECT ST_AsGeoJSON(
                    ST_Buffer(geom::geography, :distance)::geometry
                ) AS geometry
                FROM features
                WHERE id = :feature_id
            """),
            {
                "feature_id": feature_id,
                "distance": distance
            }
        )
 
        row = result.fetchone()
 
        return {
            "success": True,
            "operation": "buffer",
            "geometry": row.geometry
        }
 
    finally:
        conn.close()
 
 
# ===================================================
# Centroid FEATURE
# ===================================================
 
def centroid_feature(feature_id):
 
    conn = engine.connect()
 
    try:
 
        result = conn.execute(
            text("""
                SELECT ST_AsGeoJSON(
                    ST_Centroid(geom)
                ) AS geometry
                FROM features
                WHERE id = :feature_id
            """),
            {
                "feature_id": feature_id
            }
        )
 
        row = result.fetchone()
 
        return {
            "success": True,
            "operation": "centroid",
            "geometry": row.geometry
        }
 
    finally:
        conn.close()
 
 
# ===================================================
# Convex Hull FEATURE
# ===================================================
 
 
def convex_hull(feature_ids):
 
    if len(feature_ids) < 2:
        return {
            "success": False,
            "message": "At least two features are required for convex hull"
        }
 
    conn = engine.connect()
 
    try:
 
        result = conn.execute(
            text("""
                SELECT
                    ST_AsGeoJSON(
                        ST_ConvexHull(
                            ST_Collect(geom)
                        )
                    ) AS geometry
                FROM features
                WHERE id = ANY(:feature_ids)
            """),
            {
                "feature_ids": feature_ids
            }
        )
 
        row = result.fetchone()
 
        return {
            "success": True,
            "operation": "convex_hull",
            "geometry": row.geometry
        }
 
    finally:
        conn.close()
 
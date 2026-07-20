import json

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, DataError, SQLAlchemyError

from database.database import engine
from schemas.feature_schema import FeatureCreate
from utils.logger import logger
from utils.exception_handler import (
    NotFoundError,
    BadRequestError,
    UnprocessableEntityError,
    ServiceUnavailableError,
)

from services.case_service import create_untitled_case
from services.layer_service import create_untitled_layer


# ===================================================
# HELPERS
# ===================================================

def _create_auto_layer(case_id: int):
    return create_untitled_layer(case_id)


def _row_to_feature_dict(row):
    try:
        geometry = json.loads(row.geometry) if row.geometry else None
    except (TypeError, ValueError) as e:
        logger.error(f"Malformed geometry JSON for feature_id={row.id} | error={e}")
        geometry = None

    return {
        "id": row.id,
        "layer_id": row.layer_id,
        "name": row.name,
        "geometry_type": row.geometry_type,
        "radius": row.radius,
        "geometry": geometry,
        "properties": row.properties,
        "created_by": row.created_by,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


# ===================================================
# CREATE FEATURE
# ===================================================

def create_feature(feature):

    logger.info(
        f"Creating feature | geometry_type={feature.geometry_type} | "
        f"case_id={feature.case_id} | layer_id={feature.layer_id}"
    )

    # ---------------------------------
    # 1. CREATE CASE ONLY IF NOT PROVIDED
    # ---------------------------------
    case_id = feature.case_id or None

    if case_id is None:
        case_id = create_untitled_case(feature.created_by)

    # ---------------------------------
    # 2. CREATE NEW LAYER ONLY IF NOT PROVIDED
    # ---------------------------------
    layer_id = feature.layer_id or None

    if layer_id is None:
        layer_id = _create_auto_layer(case_id)

    # ---------------------------------
    # 3. VALIDATE GEOMETRY INPUT BEFORE HITTING THE DB
    # ---------------------------------
    if feature.geometry_type == "Circle":
        if not feature.center or "lat" not in feature.center or "lng" not in feature.center:
            logger.warning(f"Feature creation rejected: Circle missing center | layer_id={layer_id}")
            raise BadRequestError("Circle features require a 'center' with lat/lng")
        if feature.radius is None:
            logger.warning(f"Feature creation rejected: Circle missing radius | layer_id={layer_id}")
            raise BadRequestError("Circle features require a 'radius'")
    else:
        if not feature.geometry:
            logger.warning(
                f"Feature creation rejected: missing geometry | "
                f"layer_id={layer_id} | geometry_type={feature.geometry_type}"
            )
            raise BadRequestError("'geometry' is required for this geometry_type")

    # ---------------------------------
    # 4. INSERT FEATURE
    # ---------------------------------
    try:
        with engine.begin() as conn:

            if feature.geometry_type == "Circle":

                result = conn.execute(
                    text("""
                        INSERT INTO features
                        (
                            layer_id,
                            name,
                            geom,
                            geometry_type,
                            radius,
                            properties,
                            created_by
                        )
                        VALUES
                        (
                            :layer_id,
                            :name,

                            ST_Transform(
                                ST_Buffer(
                                    ST_Transform(
                                        ST_SetSRID(
                                            ST_Point(:lng, :lat),
                                            4326
                                        ),
                                        3857
                                    ),
                                    :radius
                                ),
                                4326
                            ),

                            'Circle',

                            :radius,

                            CAST(:properties AS jsonb),

                            :created_by
                        )

                        RETURNING id
                    """),
                    {
                        "layer_id": layer_id,
                        "name": feature.name,
                        "lat": feature.center["lat"],
                        "lng": feature.center["lng"],
                        "radius": feature.radius,
                        "properties": json.dumps(feature.properties),
                        "created_by": feature.created_by
                    }
                )

            else:

                result = conn.execute(
                    text("""
                        INSERT INTO features
                        (
                            layer_id,
                            name,
                            geom,
                            geometry_type,
                            radius,
                            properties,
                            created_by
                        )
                        VALUES
                        (
                            :layer_id,
                            :name,
                            ST_SetSRID(
                                ST_GeomFromGeoJSON(:geometry),
                                4326
                            ),
                            :geometry_type,
                            NULL,
                            CAST(:properties AS jsonb),
                            :created_by
                        )

                        RETURNING id
                    """),
                    {
                        "layer_id": layer_id,
                        "name": feature.name,
                        "geometry": json.dumps(feature.geometry),
                        "geometry_type": feature.geometry_type,
                        "properties": json.dumps(feature.properties),
                        "created_by": feature.created_by
                    }
                )

            feature_id = result.scalar()

    except IntegrityError as e:
        logger.error(f"Integrity error creating feature | layer_id={layer_id} | error={e}", exc_info=True)
        raise BadRequestError("Invalid reference — the specified layer_id does not exist") from e

    except DataError as e:
        logger.error(f"Data error creating feature (bad geometry?) | layer_id={layer_id} | error={e}", exc_info=True)
        raise UnprocessableEntityError("Invalid geometry data") from e

    except SQLAlchemyError as e:
        logger.error(f"Unexpected DB error creating feature | layer_id={layer_id} | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to create feature") from e

    logger.info(f"Feature created | feature_id={feature_id} | case_id={case_id} | layer_id={layer_id}")

    return {
        "success": True,
        "feature_id": feature_id,
        "case_id": case_id,
        "layer_id": layer_id
    }


# ===================================================
# GET ALL FEATURES
# ===================================================

def get_features():

    logger.info("Fetching all features")

    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT
                        id,
                        layer_id,
                        name,
                        geometry_type,
                        radius,
                        ST_AsGeoJSON(geom) AS geometry,
                        properties,
                        created_by,
                        created_at,
                        updated_at
                    FROM features
                    ORDER BY id
                """)
            )
            rows = list(result)

    except SQLAlchemyError as e:
        logger.error(f"Failed to fetch features | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to fetch features") from e

    return [_row_to_feature_dict(row) for row in rows]


# ===================================================
# GET FEATURES OF A LAYER
# ===================================================

def get_layer_features(layer_id):

    logger.info(f"Fetching features for layer | layer_id={layer_id}")

    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT
                        id,
                        layer_id,
                        name,
                        geometry_type,
                        radius,
                        ST_AsGeoJSON(geom) AS geometry,
                        properties,
                        created_by,
                        created_at,
                        updated_at
                    FROM features
                    WHERE layer_id = :layer_id
                    ORDER BY id
                """),
                {"layer_id": layer_id}
            )
            rows = list(result)

    except SQLAlchemyError as e:
        logger.error(f"Failed to fetch features for layer | layer_id={layer_id} | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to fetch features") from e

    return [_row_to_feature_dict(row) for row in rows]


# ===================================================
# GET SINGLE FEATURE
# ===================================================
# NOTE: this was missing from the pasted version, but api/features.py
# calls get_feature(feature_id) to check existence before PUT/DELETE —
# without it the router would fail to import. Restored here, matching
# the read-only, no-raise contract the router expects (returns None on
# not-found; the router itself raises NotFoundError).

def get_feature(feature_id):

    logger.info(f"Fetching feature | feature_id={feature_id}")

    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT
                        id,
                        layer_id,
                        name,
                        geometry_type,
                        radius,
                        ST_AsGeoJSON(geom) AS geometry,
                        properties,
                        created_by,
                        created_at,
                        updated_at
                    FROM features
                    WHERE id = :id
                """),
                {"id": feature_id}
            )
            row = result.fetchone()

    except SQLAlchemyError as e:
        logger.error(f"Failed to fetch feature | feature_id={feature_id} | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to fetch feature") from e

    if row is None:
        return None

    return _row_to_feature_dict(row)


# ===================================================
# UPDATE FEATURE
# ===================================================

def update_feature(feature_id, feature):

    logger.info(f"Updating feature | feature_id={feature_id}")

    try:
        with engine.begin() as conn:

            result = conn.execute(
                text("""
                    UPDATE features
                    SET
                        layer_id = :layer_id,
                        name = :name,
                        geom = ST_SetSRID(ST_GeomFromGeoJSON(:geometry), 4326),
                        properties = CAST(:properties AS jsonb),
                        updated_at = NOW()
                    WHERE id = :id
                """),
                {
                    "id": feature_id,
                    "layer_id": feature.layer_id,
                    "name": feature.name,
                    "geometry": json.dumps(feature.geometry),
                    "properties": json.dumps(feature.properties)
                }
            )

            if result.rowcount == 0:
                logger.warning(f"Update feature failed: not found | feature_id={feature_id}")
                raise NotFoundError("Feature not found")

    except NotFoundError:
        raise

    except IntegrityError as e:
        logger.error(f"Integrity error updating feature | feature_id={feature_id} | error={e}", exc_info=True)
        raise BadRequestError("Invalid layer_id — referenced layer does not exist") from e

    except DataError as e:
        logger.error(f"Data error updating feature (bad geometry?) | feature_id={feature_id} | error={e}", exc_info=True)
        raise UnprocessableEntityError("Invalid geometry data") from e

    except SQLAlchemyError as e:
        logger.error(f"Unexpected DB error updating feature | feature_id={feature_id} | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to update feature") from e

    logger.info(f"Feature updated | feature_id={feature_id}")

    return {
        "success": True,
        "message": "Feature updated successfully"
    }


# ===================================================
# PATCH FEATURE
# ===================================================

def patch_feature(feature_id, feature):

    logger.info(f"Patching feature | feature_id={feature_id}")

    try:
        with engine.begin() as conn:

            result = conn.execute(
                text("""
                    SELECT name, properties
                    FROM features
                    WHERE id = :id
                """),
                {"id": feature_id}
            )

            row = result.fetchone()

            if row is None:
                logger.warning(f"Patch feature failed: not found | feature_id={feature_id}")
                raise NotFoundError("Feature not found")

            name = feature.name if feature.name is not None else row.name

            properties = row.properties or {}

            if feature.properties is not None:
                properties.update(feature.properties)

            conn.execute(
                text("""
                    UPDATE features
                    SET
                        name = :name,
                        properties = CAST(:properties AS jsonb),
                        updated_at = NOW()
                    WHERE id = :id
                """),
                {
                    "id": feature_id,
                    "name": name,
                    "properties": json.dumps(properties)
                }
            )

    except NotFoundError:
        raise

    except SQLAlchemyError as e:
        logger.error(f"Unexpected DB error patching feature | feature_id={feature_id} | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to update feature") from e

    logger.info(f"Feature patched | feature_id={feature_id}")

    return {
        "success": True,
        "message": "Feature updated successfully"
    }


# ===================================================
# DELETE FEATURE
# ===================================================

def delete_feature(feature_id):

    logger.warning(f"Deleting feature | feature_id={feature_id}")

    try:
        with engine.begin() as conn:

            result = conn.execute(
                text("""
                    DELETE FROM features
                    WHERE id = :id
                """),
                {"id": feature_id}
            )

            if result.rowcount == 0:
                logger.warning(f"Delete feature failed: not found | feature_id={feature_id}")
                raise NotFoundError("Feature not found")

    except NotFoundError:
        raise

    except SQLAlchemyError as e:
        logger.error(f"Unexpected DB error deleting feature | feature_id={feature_id} | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to delete feature") from e

    logger.info(f"Feature deleted | feature_id={feature_id}")

    return {
        "success": True,
        "message": "Feature deleted successfully"
    }


# ===================================================
# IMPORT GEOJSON FEATURES
# ===================================================

def import_geojson_features(
    case_id: int,
    layer_id: int,
    geojson: dict,
    created_by: int = None
):

    logger.info(f"Importing GeoJSON features | case_id={case_id} | layer_id={layer_id}")

    imported = 0

    for item in geojson["features"]:

        geometry = item.get("geometry")

        if geometry is None:
            continue

        properties = item.get("properties", {})

        name = (
            properties.get("Name")
            or properties.get("name")
            or f"Imported Feature {imported + 1}"
        )

        feature = FeatureCreate(
            case_id=case_id,
            layer_id=layer_id,
            name=name,
            geometry=geometry,
            geometry_type=geometry["type"],
            properties=properties,
            created_by=created_by
        )

        create_feature(feature)

        imported += 1

    logger.info(f"GeoJSON import complete | case_id={case_id} | layer_id={layer_id} | imported={imported}")

    return {
        "success": True,
        "imported_features": imported
    }
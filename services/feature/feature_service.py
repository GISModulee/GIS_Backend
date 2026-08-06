import json

from datetime import datetime

from geoalchemy2 import Geography, Geometry
from sqlalchemy import cast, exists, func, select
from sqlalchemy.exc import IntegrityError, DataError, SQLAlchemyError

from models.model import Comment, Feature, Layer, Case
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

from services.layer.layer_service import create_untitled_layer


# ===================================================
# HELPERS
# ===================================================

async def _create_auto_layer(case_id: int, db):
    return await create_untitled_layer(case_id, db)


async def _row_to_feature_dict(row):
    try:
        geometry = json.loads(row.geometry) if row.geometry else None
    except (TypeError, ValueError) as e:
        logger.error(f"Malformed geometry JSON for feature_id={row.id} | error={e}")
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
        "has_comments": bool(row.has_comments),
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
        select(exists().where(
            Comment.case_id == Feature.case_id,
            Comment.layer_id == Feature.layer_id,
            Comment.feature_number == Feature.feature_number,
        )).scalar_subquery().label("has_comments"),
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





# ===================================================
# GET FEATURES OF A CASE
# ===================================================

async def get_case_features(case_id, db):

    logger.info(
        f"Fetching features for case | case_id={case_id}"
    )

    try:
        case_exists = db.scalar(
            select(Case.id).where(
                Case.id == case_id
            )
        )

        if case_exists is None:
            logger.warning(
                f"Get case features failed: case not found | case_id={case_id}"
            )
            raise NotFoundError(CASE_NOT_FOUND)

        result = db.execute(
            (await _feature_select())
            .where(
                Feature.case_id == case_id
            )
            .order_by(
                Feature.feature_number
            )
        )

        rows = list(result)

    except NotFoundError:
        raise

    except SQLAlchemyError as e:
        logger.error(
            f"Failed to fetch case features | case_id={case_id} | error={e}",
            exc_info=True
        )
        raise ServiceUnavailableError(
            FEATURES_FETCH_FAILED
        ) from e

    return [
        await _row_to_feature_dict(row)
        for row in rows
    ]

# ===================================================
# GET ALL FEATURES
# ===================================================

async def get_features(db):

    logger.info("Fetching all features")

    try:
        result = db.execute((await _feature_select()).order_by(Feature.id))
        rows = list(result)

    except SQLAlchemyError as e:
        logger.error(f"Failed to fetch features | error={e}", exc_info=True)
        raise ServiceUnavailableError(FEATURES_FETCH_FAILED) from e

    return [await _row_to_feature_dict(row) for row in rows]

# ===================================================
# GET SINGLE FEATURE BY NUMBER (scoped to case + layer)
# ===================================================

async def get_feature_by_number(case_id, layer_id, feature_number, db):

    logger.info(
        f"Fetching feature by number | case_id={case_id} | layer_id={layer_id} | feature_number={feature_number}"
    )

    try:
        row = db.execute(
            (await _feature_select()).where(
                Feature.case_id == case_id,
                Feature.layer_id == layer_id,
                Feature.feature_number == feature_number,
            )
        ).one_or_none()

    except SQLAlchemyError as e:
        logger.error(
            f"Failed to fetch feature by number | case_id={case_id} | layer_id={layer_id} | "
            f"feature_number={feature_number} | error={e}",
            exc_info=True
        )
        raise ServiceUnavailableError(FEATURE_FETCH_FAILED) from e

    if row is None:
        return None

    return await _row_to_feature_dict(row)

# ===================================================
# GET FEATURES OF A LAYER
# ===================================================
# FIX: previously ran the query with no check that layer_id exists.
# A nonexistent layer_id returned an empty list `[]` — indistinguishable
# from a real layer with zero features. Now verifies the layer exists
# first and raises NotFoundError (404) if not.
#
# UPDATED: now returns a minimal summary (id, feature_number, case_id,
# layer_id only) instead of the full feature dict — geometry and other
# metadata are intentionally omitted from this list view. Use
# get_feature_by_number() for full details on a single feature.

async def get_layer_features(layer_id, db):

    logger.info(f"Fetching features for layer | layer_id={layer_id}")

    try:
        layer_exists = db.scalar(select(Layer.id).where(Layer.id == layer_id))
        if layer_exists is None:
            logger.warning(f"Get layer features failed: layer not found | layer_id={layer_id}")
            raise NotFoundError(LAYER_NOT_FOUND)

        result = db.execute(
            (await _feature_select()).where(Feature.layer_id == layer_id).order_by(Feature.id)
        )
        rows = list(result)

    except NotFoundError:
        raise

    except SQLAlchemyError as e:
        logger.error(f"Failed to fetch features for layer | layer_id={layer_id} | error={e}", exc_info=True)
        raise ServiceUnavailableError(FEATURES_FETCH_FAILED) from e

    return [await _row_to_feature_summary_dict(row) for row in rows]


# ===================================================
# GET SINGLE FEATURE
# ===================================================

async def get_feature(feature_id, db):

    logger.info(f"Fetching feature | feature_id={feature_id}")

    try:
        row = db.execute(
            (await _feature_select()).where(Feature.id == feature_id)
        ).one_or_none()

    except SQLAlchemyError as e:
        logger.error(f"Failed to fetch feature | feature_id={feature_id} | error={e}", exc_info=True)
        raise ServiceUnavailableError(FEATURE_FETCH_FAILED) from e

    if row is None:
        return None

    return await _row_to_feature_dict(row)


# ===================================================
# UPDATE FEATURE
# ===================================================

async def update_feature(feature_id, feature, db):

    logger.info(f"Updating feature | feature_id={feature_id}")

    try:
        existing = db.get(Feature, feature_id)
        if existing is None:
            logger.warning(f"Update feature failed: not found | feature_id={feature_id}")
            raise NotFoundError(FEATURE_NOT_FOUND)
        existing.layer_id = feature.layer_id
        existing.name = feature.name
        existing.geom = func.ST_SetSRID(
            func.ST_GeomFromGeoJSON(json.dumps(feature.geometry)), 4326
        )
        existing.geometry_type = await _resolved_geometry_type(feature)
        existing.properties = feature.properties
        existing.updated_at = datetime.now()
        db.commit()

    except NotFoundError:
        raise

    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error updating feature | feature_id={feature_id} | error={e}", exc_info=True)
        raise NotFoundError(FEATURE_LAYER_DOES_NOT_EXIST) from e

    except DataError as e:
        db.rollback()
        logger.error(f"Data error updating feature (bad geometry?) | feature_id={feature_id} | error={e}", exc_info=True)
        raise UnprocessableEntityError(FEATURE_INVALID_GEOMETRY) from e

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Unexpected DB error updating feature | feature_id={feature_id} | error={e}", exc_info=True)
        raise ServiceUnavailableError(FEATURE_UPDATE_FAILED) from e

    logger.info(f"Feature updated | feature_id={feature_id}")

    return {
        "success": True,
        "message": "Feature updated successfully"
    }


# ===================================================
# PATCH FEATURE
# ===================================================

async def patch_feature(feature_id, feature, db):

    logger.info(f"Patching feature | feature_id={feature_id}")

    try:
        existing = db.get(Feature, feature_id)

        if existing is None:
            logger.warning(f"Patch feature failed: not found | feature_id={feature_id}")
            raise NotFoundError(FEATURE_NOT_FOUND)

        # ===================================================
        # MOVE FEATURE TO ANOTHER LAYER (OPTIONAL)
        # ===================================================
        if feature.layer_id is not None:

            destination_layer = db.get(Layer, feature.layer_id)

            if destination_layer is None:
                logger.warning(
                    f"Patch feature failed: destination layer not found | "
                    f"layer_id={feature.layer_id}"
                )
                raise NotFoundError(LAYER_NOT_FOUND)

            if destination_layer.case_id != existing.case_id:
                logger.warning(
                    f"Patch feature failed: destination layer belongs to different case | "
                    f"feature_id={feature_id} | "
                    f"feature_case={existing.case_id} | "
                    f"layer_case={destination_layer.case_id}"
                )
                raise BadRequestError(
                    "Destination layer does not belong to the same case"
                )

            existing.layer_id = feature.layer_id

        # ===================================================
        # RENAME FEATURE (OPTIONAL)
        # ===================================================
        if feature.name is not None:
            existing.name = feature.name

        # ===================================================
        # UPDATE FEATURE PROPERTIES (OPTIONAL)
        # ===================================================
        properties = dict(existing.properties or {})

        if feature.properties is not None:
            properties.update(feature.properties)

        existing.properties = properties

        existing.updated_at = datetime.now()

        db.commit()

    except NotFoundError:
        raise

    except BadRequestError:
        raise

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(
            f"Unexpected DB error patching feature | "
            f"feature_id={feature_id} | error={e}",
            exc_info=True
        )
        raise ServiceUnavailableError(FEATURE_UPDATE_FAILED) from e

    logger.info(f"Feature patched | feature_id={feature_id}")

    return {
        "success": True,
        "message": "Feature updated successfully"
    }


# ===================================================
# DELETE FEATURE
# ===================================================

async def delete_feature(feature_id, db):

    logger.warning(f"Deleting feature | feature_id={feature_id}")

    try:
        existing = db.get(Feature, feature_id)
        if existing is None:
            logger.warning(f"Delete feature failed: not found | feature_id={feature_id}")
            raise NotFoundError(FEATURE_NOT_FOUND)
        db.delete(existing)
        db.commit()

    except NotFoundError:
        raise

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Unexpected DB error deleting feature | feature_id={feature_id} | error={e}", exc_info=True)
        raise ServiceUnavailableError(FEATURE_DELETE_FAILED) from e

    logger.info(f"Feature deleted | feature_id={feature_id}")

    return {
        "success": True,
        "message": "Feature deleted successfully"
    }

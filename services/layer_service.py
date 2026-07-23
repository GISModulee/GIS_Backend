from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from database.database import engine
from utils.logger import logger
from utils.exception_handler import (
    NotFoundError,
    BadRequestError,
    ServiceUnavailableError,
)


# ===================================================
# CREATE LAYER
# ===================================================

def create_layer(layer: dict):

    logger.info(f"Creating layer | case_id={layer.get('case_id')} | name={layer.get('name')}")

    # ---------------------------------------------------------------
    # PAPER-OVER for frontend duplicate-layer bug:
    # The frontend currently fires a POST /layers with layer_type
    # "group" (client-generated name, e.g. "Auto Layer 1") right
    # around the same time it triggers feature creation, which
    # separately auto-creates a real "auto" layer with the SAME name
    # for the SAME case_id via create_untitled_layer(). That's two
    # layer rows for one user action.
    #
    # Rather than insert a second row for "group", reuse whichever
    # layer already exists for this case_id + name (the "auto" layer,
    # if it's already been created). If nothing matches yet, fall
    # through to a normal insert so this never silently drops a
    # legitimate request.
    #
    # NOTE: this hides the symptom, not the root cause — the frontend
    # should stop calling POST /layers with layer_type "group" before
    # drawing a feature. Remove this block once that's fixed.
    # ---------------------------------------------------------------
    if layer.get("layer_type") == "group":

        try:
            with engine.connect() as conn:
                existing = conn.execute(
                    text("""
                        SELECT id
                        FROM layers
                        WHERE case_id = :case_id
                          AND name = :name
                        ORDER BY created_at DESC
                        LIMIT 1
                    """),
                    {
                        "case_id": layer.get("case_id"),
                        "name": layer.get("name")
                    }
                ).fetchone()

        except SQLAlchemyError as e:
            logger.error(
                f"Failed to check for reusable layer | case_id={layer.get('case_id')} | "
                f"name={layer.get('name')} | error={e}",
                exc_info=True
            )
            raise ServiceUnavailableError("Failed to create layer") from e

        if existing:
            logger.info(
                f"Reusing existing layer instead of creating duplicate 'group' layer | "
                f"layer_id={existing.id} | case_id={layer.get('case_id')} | name={layer.get('name')}"
            )
            return {
                "success": True,
                "layer_id": existing.id,
                "message": "Reused existing layer"
            }

    try:
        with engine.begin() as conn:

            result = conn.execute(
                text("""
                    INSERT INTO layers
                    (
                        case_id,
                        name,
                        layer_type,
                        visible
                    )
                    VALUES
                    (
                        :case_id,
                        :name,
                        :layer_type,
                        :visible
                    )
                    RETURNING id
                """),
                {
                    "case_id": layer["case_id"],
                    "name": layer["name"],
                    "layer_type": layer["layer_type"],
                    "visible": layer["visible"]
                }
            )

            layer_id = result.scalar()

    except IntegrityError as e:
        logger.error(
            f"Integrity error creating layer | case_id={layer.get('case_id')} | error={e}",
            exc_info=True
        )
        raise BadRequestError(
            f"Cannot create layer: case_id {layer.get('case_id')} does not exist."
        ) from e

    except SQLAlchemyError as e:
        logger.error(f"Failed to create layer | case_id={layer.get('case_id')} | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to create layer") from e

    logger.info(f"Layer created | layer_id={layer_id} | case_id={layer.get('case_id')}")

    return {
        "success": True,
        "layer_id": layer_id,
        "message": "Layer created successfully"
    }


# ===================================================
# GET IMPORT LAYER BY FILE HASH (duplicate-import detection)
# ===================================================

def get_import_layer_by_hash(case_id: int, file_hash: str):
    """
    Returns the existing import layer dict if this exact file was
    already imported into this case, otherwise None. Used by
    upload_service.extract_kml to avoid creating a duplicate layer +
    re-importing all its features when the same file is uploaded twice.
    """

    logger.info(f"Checking for duplicate import | case_id={case_id} | file_hash={file_hash}")

    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT id, case_id, name, layer_type, visible, created_at
                    FROM layers
                    WHERE case_id = :case_id
                      AND file_hash = :file_hash
                      AND layer_type = 'import'
                    LIMIT 1
                """),
                {"case_id": case_id, "file_hash": file_hash}
            )
            row = result.fetchone()

    except SQLAlchemyError as e:
        logger.error(f"Failed to check for duplicate import | case_id={case_id} | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to check for duplicate import") from e

    if row is None:
        return None

    return {
        "id": row.id,
        "case_id": row.case_id,
        "name": row.name,
        "layer_type": row.layer_type,
        "visible": row.visible,
        "created_at": row.created_at,
    }


# ===================================================
# CREATE IMPORT LAYER (with file_hash recorded)
# ===================================================

def create_import_layer(case_id: int, name: str, file_hash: str):

    logger.info(f"Creating import layer | case_id={case_id} | name={name} | file_hash={file_hash}")

    try:
        with engine.begin() as conn:

            result = conn.execute(
                text("""
                    INSERT INTO layers
                    (
                        case_id,
                        name,
                        layer_type,
                        visible,
                        file_hash
                    )
                    VALUES
                    (
                        :case_id,
                        :name,
                        'import',
                        TRUE,
                        :file_hash
                    )
                    RETURNING id
                """),
                {
                    "case_id": case_id,
                    "name": name,
                    "file_hash": file_hash
                }
            )

            layer_id = result.scalar()

    except IntegrityError as e:
        logger.error(f"Integrity error creating import layer | case_id={case_id} | error={e}", exc_info=True)
        raise BadRequestError(f"Cannot create layer: case_id {case_id} does not exist.") from e

    except SQLAlchemyError as e:
        logger.error(f"Failed to create import layer | case_id={case_id} | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to create layer") from e

    logger.info(f"Import layer created | layer_id={layer_id} | case_id={case_id}")

    return {
        "success": True,
        "layer_id": layer_id,
        "message": "Layer created successfully"
    }


# ===================================================
# CREATE AUTO LAYER
# ===================================================

def create_untitled_layer(case_id: int):

    logger.info(f"Creating auto layer | case_id={case_id}")

    try:
        with engine.begin() as conn:

        
            conn.execute(
                text("SELECT pg_advisory_xact_lock(:key)"),
                {"key": case_id}
            )

            result = conn.execute(
                text("""
                    SELECT COALESCE(
                        MAX(
                            CAST(
                                REPLACE(name, 'Auto Layer ', '') AS INTEGER
                            )
                        ),
                        0
                    )
                    FROM layers
                    WHERE case_id = :case_id
                      AND layer_type = 'auto'
                      AND name LIKE 'Auto Layer %'
                """),
                {
                    "case_id": case_id
                }
            )

            max_number = result.scalar()
            next_number = max_number + 1
            layer_name = f"Auto Layer {next_number}"

            result = conn.execute(
                text("""
                    INSERT INTO layers
                    (
                        case_id,
                        name,
                        layer_type,
                        visible
                    )
                    VALUES
                    (
                        :case_id,
                        :name,
                        'auto',
                        TRUE
                    )
                    RETURNING id
                """),
                {
                    "case_id": case_id,
                    "name": layer_name
                }
            )

            layer_id = result.scalar()

    except SQLAlchemyError as e:
        logger.error(f"Failed to auto-create layer | case_id={case_id} | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to auto-create layer") from e

    logger.info(f"Auto layer created | layer_id={layer_id} | case_id={case_id}")

    # IMPORTANT: feature_service.py expects only the layer ID
    return layer_id


# ===================================================
# GET ALL LAYERS
# ===================================================

def get_layers():

    logger.info("Fetching all layers")

    try:
        with engine.connect() as conn:

            result = conn.execute(
                text("""
                    SELECT
                        id,
                        case_id,
                        name,
                        layer_type,
                        visible,
                        created_at
                    FROM layers
                    ORDER BY id
                """)
            )

            return [
                {
                    "id": row.id,
                    "case_id": row.case_id,
                    "name": row.name,
                    "layer_type": row.layer_type,
                    "visible": row.visible,
                    "created_at": row.created_at
                }
                for row in result
            ]

    except SQLAlchemyError as e:
        logger.error(f"Failed to fetch layers | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to fetch layers") from e


# ===================================================
# GET SINGLE LAYER
# ===================================================

def get_layer(layer_id: int):
    """
    Kept returning None on not-found (unchanged contract) — routers do
    their own `if layer is None: raise NotFoundError(...)` before
    calling update/patch/delete. Change this to raise NotFoundError
    directly only if you also update those callers.
    """

    logger.info(f"Fetching layer | layer_id={layer_id}")

    try:
        with engine.connect() as conn:

            result = conn.execute(
                text("""
                    SELECT
                        id,
                        case_id,
                        name,
                        layer_type,
                        visible,
                        created_at
                    FROM layers
                    WHERE id = :id
                """),
                {"id": layer_id}
            )

            row = result.fetchone()

            if not row:
                return None

            return {
                "id": row.id,
                "case_id": row.case_id,
                "name": row.name,
                "layer_type": row.layer_type,
                "visible": row.visible,
                "created_at": row.created_at
            }

    except SQLAlchemyError as e:
        logger.error(f"Failed to fetch layer | layer_id={layer_id} | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to fetch layer") from e


# ===================================================
# UPDATE LAYER
# ===================================================

def update_layer(layer_id: int, layer: dict):

    logger.info(f"Updating layer | layer_id={layer_id}")

    try:
        with engine.begin() as conn:

            result = conn.execute(
                text("""
                    UPDATE layers
                    SET
                        case_id = :case_id,
                        name = :name,
                        layer_type = :layer_type,
                        visible = :visible
                    WHERE id = :id
                """),
                {
                    "id": layer_id,
                    "case_id": layer["case_id"],
                    "name": layer["name"],
                    "layer_type": layer["layer_type"],
                    "visible": layer["visible"]
                }
            )

            if result.rowcount == 0:
                logger.warning(f"Update layer failed: not found | layer_id={layer_id}")
                raise NotFoundError("Layer not found")

    except NotFoundError:
        raise

    except SQLAlchemyError as e:
        logger.error(f"Failed to update layer | layer_id={layer_id} | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to update layer") from e

    logger.info(f"Layer updated | layer_id={layer_id}")

    return {
        "success": True,
        "message": "Layer updated successfully"
    }


# ===================================================
# DELETE LAYER
# ===================================================

def delete_layer(layer_id):

    logger.warning(f"Deleting layer | layer_id={layer_id}")

    try:
        with engine.begin() as conn:

            result = conn.execute(
                text("""
                    SELECT case_id, name, layer_type
                    FROM layers
                    WHERE id = :id
                """),
                {"id": layer_id}
            )

            row = result.fetchone()

            if row is None:
                logger.warning(f"Delete layer failed: not found | layer_id={layer_id}")
                raise NotFoundError("Layer not found")

            case_id = row.case_id
            layer_name = row.name
            layer_type = row.layer_type

            deleted_number = None

            if layer_type == "auto":
                try:
                    deleted_number = int(layer_name.replace("Auto Layer ", ""))
                except (ValueError, AttributeError) as e:
                    logger.warning(
                        f"Could not parse auto layer number for renumbering | "
                        f"layer_id={layer_id} | name={layer_name} | error={e}"
                    )
                    deleted_number = None

            conn.execute(
                text("""
                    DELETE FROM layers
                    WHERE id = :id
                """),
                {"id": layer_id}
            )

            if deleted_number is not None:

                result = conn.execute(
                    text("""
                        SELECT id, name
                        FROM layers
                        WHERE case_id = :case_id
                          AND layer_type = 'auto'
                    """),
                    {"case_id": case_id}
                )

                layers = result.fetchall()

                for layer in layers:

                    try:
                        current_number = int(
                            layer.name.replace("Auto Layer ", "")
                        )

                        if current_number > deleted_number:

                            conn.execute(
                                text("""
                                    UPDATE layers
                                    SET name = :name
                                    WHERE id = :id
                                """),
                                {
                                    "id": layer.id,
                                    "name": f"Auto Layer {current_number - 1}"
                                }
                            )

                    except (ValueError, AttributeError) as e:
                        logger.warning(
                            f"Skipping renumber for layer_id={layer.id} | "
                            f"name={layer.name} | error={e}"
                        )

    except NotFoundError:
        raise

    except SQLAlchemyError as e:
        logger.error(f"Failed to delete layer | layer_id={layer_id} | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to delete layer") from e

    logger.info(f"Layer deleted | layer_id={layer_id}")

    return {
        "success": True,
        "message": "Layer deleted successfully"
    }


# ===================================================
# GET LAYERS BY CASE
# ===================================================

def get_case_layers(case_id: int):

    logger.info(f"Fetching layers for case | case_id={case_id}")

    try:
        with engine.connect() as conn:

            result = conn.execute(
                text("""
                    SELECT
                        id,
                        case_id,
                        name,
                        layer_type,
                        visible,
                        created_at
                    FROM layers
                    WHERE case_id = :case_id
                    ORDER BY id
                """),
                {"case_id": case_id}
            )

            return [
                {
                    "id": row.id,
                    "case_id": row.case_id,
                    "name": row.name,
                    "layer_type": row.layer_type,
                    "visible": row.visible,
                    "created_at": row.created_at
                }
                for row in result
            ]

    except SQLAlchemyError as e:
        logger.error(f"Failed to fetch layers for case | case_id={case_id} | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to fetch layers") from e


# ===================================================
# PATCH LAYER
# ===================================================

def patch_layer(layer_id: int, layer: dict):

    updates = []
    values = {"id": layer_id}

    if layer.get("name") is not None:
        updates.append("name = :name")
        values["name"] = layer["name"]

    if layer.get("layer_type") is not None:
        updates.append("layer_type = :layer_type")
        values["layer_type"] = layer["layer_type"]

    if layer.get("visible") is not None:
        updates.append("visible = :visible")
        values["visible"] = layer["visible"]

    if not updates:
        logger.info(f"Patch layer skipped, no fields provided | layer_id={layer_id}")
        raise BadRequestError("No fields provided to update")

    query = f"""
        UPDATE layers
        SET {", ".join(updates)}
        WHERE id = :id
    """

    logger.info(f"Patching layer | layer_id={layer_id} | fields={list(values.keys())}")

    try:
        with engine.begin() as conn:

            result = conn.execute(text(query), values)

            if result.rowcount == 0:
                logger.warning(f"Patch layer failed: not found | layer_id={layer_id}")
                raise NotFoundError("Layer not found")

    except NotFoundError:
        raise

    except SQLAlchemyError as e:
        logger.error(f"Failed to patch layer | layer_id={layer_id} | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to update layer") from e

    logger.info(f"Layer patched | layer_id={layer_id} | fields={list(values.keys())}")

    return {
        "success": True,
        "message": "Layer updated successfully"
    }

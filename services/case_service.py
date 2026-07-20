from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from database.database import engine
from utils.logger import logger
from utils.exception_handler import (
    NotFoundError,
    BadRequestError,
    ServiceUnavailableError,
)


# ===================================================
# CREATE CASE (PURE - NO SIDE EFFECTS)
# ===================================================

def create_case(case):

    logger.info(f"Creating case | title={case.title}")

    try:
        with engine.begin() as conn:

            result = conn.execute(
                text("""
                    INSERT INTO cases
                    (
                        title,
                        description,
                        status,
                        priority,
                        created_by
                    )
                    VALUES
                    (
                        :title,
                        :description,
                        'Open',
                        :priority,
                        :created_by
                    )
                    RETURNING id
                """),
                {
                    "title": case.title,
                    "description": case.description,
                    "priority": case.priority,
                    "created_by": case.created_by
                }
            )

            case_id = result.scalar()

    except SQLAlchemyError as e:
        # `with engine.begin()` already rolled back automatically on
        # exception exit — we just need to log + surface a clean error.
        logger.error(f"Failed to create case | title={case.title} | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to create case") from e

    logger.info(f"Case created | case_id={case_id} | title={case.title}")

    return {
        "success": True,
        "case_id": case_id,
        "message": "Case created successfully"
    }


# ===================================================
# GET OR CREATE DEFAULT CASE
# ===================================================

def create_untitled_case(created_by=None):

    logger.info(f"Fetching/creating untitled case | created_by={created_by}")

    try:
        with engine.begin() as conn:

            result = conn.execute(
                text("""
                    SELECT id
                    FROM cases
                    WHERE title = 'Untitled Case'
                    LIMIT 1
                """)
            )

            row = result.fetchone()

            if row:
                logger.info(f"Reusing existing untitled case | case_id={row.id}")
                return row.id

            result = conn.execute(
                text("""
                    INSERT INTO cases
                    (
                        title,
                        description,
                        status,
                        priority,
                        created_by
                    )
                    VALUES
                    (
                        'Untitled Case',
                        '',
                        'Open',
                        'Medium',
                        :created_by
                    )
                    RETURNING id
                """),
                {
                    "created_by": created_by
                }
            )

            case_id = result.scalar()

    except SQLAlchemyError as e:
        logger.error(f"Failed to auto-create untitled case | created_by={created_by} | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to auto-create default case") from e

    logger.info(f"Untitled case created | case_id={case_id}")

    return case_id


# ===================================================
# GET ALL CASES
# ===================================================

def get_cases():

    logger.info("Fetching all cases")

    try:
        with engine.connect() as conn:

            result = conn.execute(text("""
                SELECT id, title, description, status, priority, created_by, created_at
                FROM cases
                ORDER BY created_at DESC
            """))

            return [dict(row._mapping) for row in result]

    except SQLAlchemyError as e:
        logger.error(f"Failed to fetch cases | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to fetch cases") from e


# ===================================================
# GET SINGLE CASE
# ===================================================

def get_case(case_id):
    """
    Kept returning None on not-found (unchanged contract) —
    cases.py router does its own `if existing is None: raise NotFoundError(...)`
    before calling update/patch/delete. Change this to raise NotFoundError
    directly only if you also update that router to stop double-checking.
    """

    logger.info(f"Fetching case | case_id={case_id}")

    try:
        with engine.connect() as conn:

            result = conn.execute(
                text("""
                    SELECT id, title, description, status, priority, created_by, created_at
                    FROM cases
                    WHERE id = :id
                """),
                {"id": case_id}
            )

            row = result.fetchone()
            return dict(row._mapping) if row else None

    except SQLAlchemyError as e:
        logger.error(f"Failed to fetch case | case_id={case_id} | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to fetch case") from e


# ===================================================
# UPDATE CASE
# ===================================================

def update_case(case_id, case):

    logger.info(f"Updating case | case_id={case_id}")

    try:
        with engine.begin() as conn:

            result = conn.execute(
                text("""
                    UPDATE cases
                    SET
                        title = :title,
                        description = :description,
                        priority = :priority
                    WHERE id = :id
                """),
                {
                    "id": case_id,
                    "title": case.title,
                    "description": case.description,
                    "priority": case.priority
                }
            )

            if result.rowcount == 0:
                logger.warning(f"Update case failed: not found | case_id={case_id}")
                raise NotFoundError("Case not found")

    except NotFoundError:
        raise

    except SQLAlchemyError as e:
        logger.error(f"Failed to update case | case_id={case_id} | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to update case") from e

    logger.info(f"Case updated | case_id={case_id}")

    return {
        "success": True,
        "message": "Case updated successfully"
    }


# ===================================================
# PATCH CASE
# ===================================================

def patch_case(case_id, case):

    updates = []
    values = {"id": case_id}

    if case.title is not None:
        updates.append("title = :title")
        values["title"] = case.title

    if case.description is not None:
        updates.append("description = :description")
        values["description"] = case.description

    if case.priority is not None:
        updates.append("priority = :priority")
        values["priority"] = case.priority

    if not updates:
        logger.info(f"Patch case skipped, no fields provided | case_id={case_id}")
        raise BadRequestError("No fields provided to update")

    query = f"""
        UPDATE cases
        SET {", ".join(updates)}
        WHERE id = :id
    """

    logger.info(f"Patching case | case_id={case_id} | fields={list(values.keys())}")

    try:
        with engine.begin() as conn:

            result = conn.execute(text(query), values)

            if result.rowcount == 0:
                logger.warning(f"Patch case failed: not found | case_id={case_id}")
                raise NotFoundError("Case not found")

    except NotFoundError:
        raise

    except SQLAlchemyError as e:
        logger.error(f"Failed to patch case | case_id={case_id} | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to update case") from e

    logger.info(f"Case patched | case_id={case_id} | fields={list(values.keys())}")

    return {
        "success": True,
        "message": "Case updated successfully"
    }


# ===================================================
# DELETE CASE
# ===================================================

def delete_case(case_id):

    logger.warning(f"Deleting case | case_id={case_id}")

    try:
        with engine.begin() as conn:

            result = conn.execute(
                text("""
                    DELETE FROM cases
                    WHERE id = :id
                """),
                {"id": case_id}
            )

            if result.rowcount == 0:
                logger.warning(f"Delete case failed: not found | case_id={case_id}")
                raise NotFoundError("Case not found")

    except NotFoundError:
        raise

    except SQLAlchemyError as e:
        logger.error(f"Failed to delete case | case_id={case_id} | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to delete case") from e

    logger.info(f"Case deleted | case_id={case_id}")

    return {
        "success": True,
        "message": "Case deleted successfully"
    }
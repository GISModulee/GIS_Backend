from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from database.database import SessionLocal
from models.model import Case
from utils.logger import logger
from utils.exceptions import (
    NotFoundError,
    BadRequestError,
    ServiceUnavailableError,
)


def _case_dict(case: Case):
    return {
        "id": case.id,
        "title": case.title,
        "description": case.description,
        "status": case.status,
        "priority": case.priority,
        "created_by": case.created_by,
        "created_at": case.created_at,
    }


def create_case(case, created_by: int | None = None):
    logger.info(f"Creating case | title={case.title} | created_by={created_by}")
    try:
        with SessionLocal.begin() as db:
            new_case = Case(
                title=case.title,
                description=case.description,
                status="Open",
                priority=case.priority,
                created_by=created_by,
            )
            db.add(new_case)
            db.flush()
            case_id = new_case.id
    except SQLAlchemyError as e:
        logger.error(f"Failed to create case | title={case.title} | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to create case") from e
    logger.info(f"Case created | case_id={case_id} | title={case.title}")
    return {"success": True, "case_id": case_id, "message": "Case created successfully"}


def create_untitled_case(created_by=None):
    logger.info(f"Fetching/creating untitled case | created_by={created_by}")
    try:
        with SessionLocal.begin() as db:
            existing_id = db.scalar(
                select(Case.id).where(Case.title == "Untitled Case").limit(1)
            )
            if existing_id is not None:
                logger.info(f"Reusing existing untitled case | case_id={existing_id}")
                return existing_id
            new_case = Case(
                title="Untitled Case",
                description="",
                status="Open",
                priority="Medium",
                created_by=created_by,
            )
            db.add(new_case)
            db.flush()
            case_id = new_case.id
    except SQLAlchemyError as e:
        logger.error(
            f"Failed to auto-create untitled case | created_by={created_by} | error={e}",
            exc_info=True,
        )
        raise ServiceUnavailableError("Failed to auto-create default case") from e
    logger.info(f"Untitled case created | case_id={case_id}")
    return case_id


def get_cases():
    logger.info("Fetching all cases")
    try:
        with SessionLocal() as db:
            cases = db.scalars(select(Case).order_by(Case.created_at.desc())).all()
            return [_case_dict(case) for case in cases]
    except SQLAlchemyError as e:
        logger.error(f"Failed to fetch cases | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to fetch cases") from e


def get_case(case_id):
    logger.info(f"Fetching case | case_id={case_id}")
    try:
        with SessionLocal() as db:
            case = db.get(Case, case_id)
            return _case_dict(case) if case else None
    except SQLAlchemyError as e:
        logger.error(f"Failed to fetch case | case_id={case_id} | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to fetch case") from e


def update_case(case_id, case):
    logger.info(f"Updating case | case_id={case_id}")
    try:
        with SessionLocal.begin() as db:
            existing = db.get(Case, case_id)
            if existing is None:
                logger.warning(f"Update case failed: not found | case_id={case_id}")
                raise NotFoundError("Case not found")
            existing.title = case.title
            existing.description = case.description
            existing.priority = case.priority
    except NotFoundError:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Failed to update case | case_id={case_id} | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to update case") from e
    logger.info(f"Case updated | case_id={case_id}")
    return {"success": True, "message": "Case updated successfully"}


def patch_case(case_id, case):
    updates = case.model_dump(exclude_none=True)
    if not updates:
        logger.info(f"Patch case skipped, no fields provided | case_id={case_id}")
        raise BadRequestError("No fields provided to update")
    logger.info(f"Patching case | case_id={case_id} | fields={list(updates)}")
    try:
        with SessionLocal.begin() as db:
            existing = db.get(Case, case_id)
            if existing is None:
                logger.warning(f"Patch case failed: not found | case_id={case_id}")
                raise NotFoundError("Case not found")
            for field, value in updates.items():
                setattr(existing, field, value)
    except NotFoundError:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Failed to patch case | case_id={case_id} | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to update case") from e
    logger.info(f"Case patched | case_id={case_id} | fields={list(updates)}")
    return {"success": True, "message": "Case updated successfully"}


def delete_case(case_id):
    logger.warning(f"Deleting case | case_id={case_id}")
    try:
        with SessionLocal.begin() as db:
            existing = db.get(Case, case_id)
            if existing is None:
                logger.warning(f"Delete case failed: not found | case_id={case_id}")
                raise NotFoundError("Case not found")
            db.delete(existing)
    except NotFoundError:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Failed to delete case | case_id={case_id} | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to delete case") from e
    logger.info(f"Case deleted | case_id={case_id}")
    return {"success": True, "message": "Case deleted successfully"}

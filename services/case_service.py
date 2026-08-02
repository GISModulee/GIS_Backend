from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

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


def create_case(case, db, created_by: int | None = None):
    logger.info(f"Creating case | title={case.title} | created_by={created_by}")
    try:
        new_case = Case(
            title=case.title,
            description=case.description,
            status="Open",
            priority=case.priority,
            created_by=created_by,
        )
        db.add(new_case)
        db.commit()
        db.refresh(new_case)
        case_id = new_case.id
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Failed to create case | title={case.title} | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to create case") from e
    logger.info(f"Case created | case_id={case_id} | title={case.title}")
    return {"success": True, "case_id": case_id, "message": "Case created successfully"}


def get_cases(db):
    logger.info("Fetching all cases")
    try:
        cases = db.scalars(select(Case).order_by(Case.created_at.desc())).all()
        return [_case_dict(case) for case in cases]
    except SQLAlchemyError as e:
        logger.error(f"Failed to fetch cases | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to fetch cases") from e


def get_case(case_id, db):
    logger.info(f"Fetching case | case_id={case_id}")
    try:
        case = db.get(Case, case_id)
        return _case_dict(case) if case else None
    except SQLAlchemyError as e:
        logger.error(f"Failed to fetch case | case_id={case_id} | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to fetch case") from e


def update_case(case_id, case, db):
    logger.info(f"Updating case | case_id={case_id}")
    try:
        existing = db.get(Case, case_id)
        if existing is None:
            logger.warning(f"Update case failed: not found | case_id={case_id}")
            raise NotFoundError("Case not found")
        existing.title = case.title
        existing.description = case.description
        existing.priority = case.priority
        db.commit()
    except NotFoundError:
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Failed to update case | case_id={case_id} | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to update case") from e
    logger.info(f"Case updated | case_id={case_id}")
    return {"success": True, "message": "Case updated successfully"}


def patch_case(case_id, case, db):
    updates = case.model_dump(exclude_none=True)
    if not updates:
        logger.info(f"Patch case skipped, no fields provided | case_id={case_id}")
        raise BadRequestError("No fields provided to update")
    logger.info(f"Patching case | case_id={case_id} | fields={list(updates)}")
    try:
        existing = db.get(Case, case_id)
        if existing is None:
            logger.warning(f"Patch case failed: not found | case_id={case_id}")
            raise NotFoundError("Case not found")
        for field, value in updates.items():
            setattr(existing, field, value)
        db.commit()
    except NotFoundError:
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Failed to patch case | case_id={case_id} | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to update case") from e
    logger.info(f"Case patched | case_id={case_id} | fields={list(updates)}")
    return {"success": True, "message": "Case updated successfully"}


def delete_case(case_id, db):
    logger.warning(f"Deleting case | case_id={case_id}")
    try:
        existing = db.get(Case, case_id)
        if existing is None:
            logger.warning(f"Delete case failed: not found | case_id={case_id}")
            raise NotFoundError("Case not found")
        db.delete(existing)
        db.commit()
    except NotFoundError:
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Failed to delete case | case_id={case_id} | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to delete case") from e
    logger.info(f"Case deleted | case_id={case_id}")
    return {"success": True, "message": "Case deleted successfully"}

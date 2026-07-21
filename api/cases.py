from fastapi import APIRouter, Depends

from schemas.case_schema import CaseCreate, CasePatch
from utils.exception_handler import NotFoundError
from utils.dependencies import get_current_user, require_roles
from utils.roles import CAN_WRITE, CAN_DELETE_CASE

from services.case_service import (
    create_case,
    get_cases,
    get_case,
    update_case,
    delete_case,
    patch_case
)
from utils.logger import logger

router = APIRouter(prefix="/cases", tags=["Cases"])


# ===================================================
# CREATE CASE — Admin, Officer, Analyst
# ===================================================
@router.post("")
def add_case(case: CaseCreate, current_user=Depends(require_roles(CAN_WRITE))):
    logger.info(f"POST /cases | user_id={current_user['user_id']} | role={current_user['role']} | body={case.model_dump()}")
    return create_case(case)


# ===================================================
# GET ALL CASES — any authenticated user
# ===================================================
@router.get("")
def list_cases(current_user=Depends(get_current_user)):
    logger.info(f"GET /cases | user_id={current_user['user_id']}")
    return get_cases()


# ===================================================
# GET SINGLE CASE — any authenticated user
# ===================================================
@router.get("/{case_id}")
def get_single_case(case_id: int, current_user=Depends(get_current_user)):

    logger.info(f"GET /cases/{case_id} | user_id={current_user['user_id']}")

    case = get_case(case_id)

    if case is None:
        logger.warning(f"Case not found | case_id={case_id}")
        raise NotFoundError("Case not found")

    return case


# ===================================================
# UPDATE CASE — Admin, Officer, Analyst
# ===================================================
@router.put("/{case_id}")
def edit_case(case_id: int, case: CaseCreate, current_user=Depends(require_roles(CAN_WRITE))):

    logger.info(f"PUT /cases/{case_id} | user_id={current_user['user_id']} | role={current_user['role']}")

    existing = get_case(case_id)

    if existing is None:
        logger.warning(f"Case not found | case_id={case_id}")
        raise NotFoundError("Case not found")

    return update_case(case_id, case)


# ===================================================
# PATCH CASE — Admin, Officer, Analyst
# ===================================================
@router.patch("/{case_id}")
def edit_case_partial(case_id: int, case: CasePatch, current_user=Depends(require_roles(CAN_WRITE))):

    logger.info(f"PATCH /cases/{case_id} | user_id={current_user['user_id']} | role={current_user['role']}")

    existing = get_case(case_id)

    if existing is None:
        logger.warning(f"Case not found | case_id={case_id}")
        raise NotFoundError("Case not found")

    return patch_case(case_id, case)


# ===================================================
# DELETE CASE — Admin only
# ===================================================
@router.delete("/{case_id}")
def remove_case(case_id: int, current_user=Depends(require_roles(CAN_DELETE_CASE))):

    logger.warning(f"DELETE /cases/{case_id} | user_id={current_user['user_id']} | role={current_user['role']}")

    existing = get_case(case_id)

    if existing is None:
        logger.warning(f"Case not found | case_id={case_id}")
        raise NotFoundError("Case not found")

    return delete_case(case_id)
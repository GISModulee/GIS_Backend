from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database.database import get_db
from schemas.case_schema import CaseActionResponse, CaseCreate, CaseCreateResponse, CasePatch, CaseResponse
from utils.constants import CASE_NOT_FOUND
from utils.exceptions import NotFoundError
from utils.dependencies import get_current_user, require_roles
from utils.roles import CAN_WRITE, CAN_DELETE_CASE

from services.case.case_service import (
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
@router.post("", response_model=CaseCreateResponse)
async def add_case(case: CaseCreate, db: Session = Depends(get_db), current_user=Depends(require_roles(CAN_WRITE))):
    logger.info(f"POST /cases | user_id={current_user['user_id']} | role={current_user['role']} | body={case.model_dump()}")
    return await create_case(case, db, current_user["user_id"])


# ===================================================
# GET ALL CASES — any authenticated user
# ===================================================
@router.get("", response_model=list[CaseResponse])
async def list_cases(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    logger.info(f"GET /cases | user_id={current_user['user_id']}")
    return await get_cases(db)


# ===================================================
# GET SINGLE CASE — any authenticated user
# ===================================================
@router.get("/{case_id}", response_model=CaseResponse)
async def get_single_case(case_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):

    logger.info(f"GET /cases/{case_id} | user_id={current_user['user_id']}")

    case = await get_case(case_id, db)

    if case is None:
        logger.warning(f"Case not found | case_id={case_id}")
        raise NotFoundError(CASE_NOT_FOUND)

    return case


# ===================================================
# UPDATE CASE — Admin, Officer, Analyst
# ===================================================
@router.put("/{case_id}", response_model=CaseActionResponse)
async def edit_case(case_id: int, case: CaseCreate, db: Session = Depends(get_db), current_user=Depends(require_roles(CAN_WRITE))):

    logger.info(f"PUT /cases/{case_id} | user_id={current_user['user_id']} | role={current_user['role']}")

    existing = await get_case(case_id, db)

    if existing is None:
        logger.warning(f"Case not found | case_id={case_id}")
        raise NotFoundError(CASE_NOT_FOUND)

    return await update_case(case_id, case, db)


# ===================================================
# PATCH CASE — Admin, Officer, Analyst
# ===================================================
@router.patch("/{case_id}", response_model=CaseActionResponse)
async def edit_case_partial(case_id: int, case: CasePatch, db: Session = Depends(get_db), current_user=Depends(require_roles(CAN_WRITE))):

    logger.info(f"PATCH /cases/{case_id} | user_id={current_user['user_id']} | role={current_user['role']}")

    existing = await get_case(case_id, db)

    if existing is None:
        logger.warning(f"Case not found | case_id={case_id}")
        raise NotFoundError(CASE_NOT_FOUND)

    return await patch_case(case_id, case, db)


# ===================================================
# DELETE CASE — Admin only
# ===================================================
@router.delete("/{case_id}", response_model=CaseActionResponse)
async def remove_case(case_id: int, db: Session = Depends(get_db), current_user=Depends(require_roles(CAN_DELETE_CASE))):

    logger.warning(f"DELETE /cases/{case_id} | user_id={current_user['user_id']} | role={current_user['role']}")

    existing = await get_case(case_id, db)

    if existing is None:
        logger.warning(f"Case not found | case_id={case_id}")
        raise NotFoundError(CASE_NOT_FOUND)

    return await delete_case(case_id, db)

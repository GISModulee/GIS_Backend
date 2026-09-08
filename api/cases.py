from fastapi import APIRouter, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from schemas.case_schema import CaseResponse
from utils.exceptions import UnauthorizedError
from utils.dependencies import get_current_user
from utils.ci_client import get_user_cases
from utils.logger import logger

security = HTTPBearer(auto_error=False)

router = APIRouter(prefix="/cases", tags=["Cases"])


# ===================================================
# CREATE CASE — REMOVED
# Case creation is now owned by Central Intelligence.
# CI assigns case_id; GIS no longer creates cases locally.
# ===================================================


# ===================================================
# GET ALL CASES — any authenticated user
# Cases fetched from Central Intelligence (user's assigned cases only)
# ===================================================
@router.get("", response_model=list[CaseResponse])
async def list_cases(
    current_user=Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials | None = Depends(security)
):
    logger.info(f"GET /cases | user_id={current_user['user_id']}")
    if credentials is None:
        logger.warning("GET /cases - No credentials provided")
        raise UnauthorizedError("Authentication required")
    return await get_user_cases(credentials.credentials)


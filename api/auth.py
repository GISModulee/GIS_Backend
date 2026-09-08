from fastapi import APIRouter, Depends

from schemas.auth_schema import CurrentUserResponse
from utils.dependencies import get_current_user
from utils.logger import logger

router = APIRouter(tags=["Authentication"])


@router.get("/me", response_model=CurrentUserResponse)
async def get_me(current_user=Depends(get_current_user)):
    logger.info(f"GET /me | user_id={current_user['user_id']}")
    return current_user
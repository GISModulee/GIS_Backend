from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database.database import get_db
from schemas.auth_schema import (
    RegisterUser,
    LoginUser,
    RegisterResponse,
    TokenResponse,
    CurrentUserResponse,
)
from services.auth_service import (
    register_user,
    login_user
)
from utils.dependencies import get_current_user
from utils.logger import logger

router = APIRouter(tags=["Authentication"])


@router.post("/register", response_model=RegisterResponse)
def register(user: RegisterUser, db: Session = Depends(get_db)):
    logger.info(f"POST /register | email={user.email} | role={user.role}")
    return register_user(user, db)


@router.post("/login", response_model=TokenResponse)
def login(user: LoginUser, db: Session = Depends(get_db)):
    logger.info(f"POST /login | email={user.email}")
    return login_user(user, db)


@router.get("/me", response_model=CurrentUserResponse)
def get_me(current_user=Depends(get_current_user)):
    logger.info(f"GET /me | user_id={current_user['user_id']}")
    return current_user

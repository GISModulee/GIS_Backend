from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import text

from database.database import engine
from utils.config import settings
from utils.exception_handler import UnauthorizedError
from utils.logger import logger

# ===================================================
# OAuth2
# ===================================================

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/login"
)


# ===================================================
# CREATE ACCESS TOKEN
# ===================================================

def create_access_token(
    user_id: int,
    email: str,
    role: str
) -> str:

    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "exp": expire
    }

    token = jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )

    logger.info(
        f"JWT created | user_id={user_id} | role={role}"
    )

    return token


# ===================================================
# VERIFY TOKEN
# ===================================================

def verify_token(token: str):

    try:

        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )

        return payload

    except JWTError as e:

        logger.warning(f"Invalid JWT token | error={e}")

        raise UnauthorizedError(
            "Invalid or expired token."
        )


# ===================================================
# GET CURRENT USER
# ===================================================

def get_current_user(
    token: str = Depends(oauth2_scheme)
):

    payload = verify_token(token)

    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError) as e:
        logger.warning(f"Malformed JWT payload | error={e}")
        raise UnauthorizedError("Invalid token payload.")

    with engine.connect() as conn:

        result = conn.execute(
            text("""
                SELECT
                    id,
                    username,
                    email,
                    full_name,
                    role,
                    created_at,
                    last_login
                FROM users
                WHERE id = :id
            """),
            {
                "id": user_id
            }
        )

        user = result.fetchone()

    if user is None:

        logger.warning(
            f"User from token not found | user_id={user_id}"
        )

        raise UnauthorizedError(
            "User not found."
        )

    return user


# ===================================================
# ROLE CHECK
# ===================================================

def require_roles(
    allowed_roles: List[str]
):
   
    def checker(
        current_user=Depends(get_current_user)
    ):

        if current_user.role not in allowed_roles:

            logger.warning(
                f"Permission denied | "
                f"user={current_user.email} "
                f"role={current_user.role} "
                f"required={allowed_roles}"
            )

            from utils.exception_handler import ForbiddenError
            raise ForbiddenError(
                "You do not have permission to perform this action."
            )

        return current_user

    return checker

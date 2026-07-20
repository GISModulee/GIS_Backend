from typing import List

from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from utils.auth_utils import decode_access_token
from utils.exception_handler import UnauthorizedError, ForbiddenError
from utils.logger import logger

security = HTTPBearer()


# ===================================================
# GET CURRENT USER
# ===================================================
# Any route that adds `Depends(get_current_user)` now requires a valid
# `Authorization: Bearer <token>` header. HTTPBearer() itself returns a
# 403 if the header is missing entirely (FastAPI's own behavior); if
# it's present but the token is invalid/expired, decode_access_token
# returns None and we raise a proper 401 here.

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials

    payload = decode_access_token(token)

    if payload is None:
        raise UnauthorizedError("Invalid or expired token.")

    user_id = payload.get("user_id")
    email = payload.get("sub")
    role = payload.get("role")

    if user_id is None or email is None:
        logger.warning(f"Malformed JWT payload | payload={payload}")
        raise UnauthorizedError("Invalid token payload.")

    return {
        "user_id": user_id,
        "email": email,
        "role": role
    }


def require_roles(allowed_roles: List[str]):

    def checker(current_user=Depends(get_current_user)):

        if current_user["role"] not in allowed_roles:
            logger.warning(
                f"Permission denied | user={current_user['email']} "
                f"role={current_user['role']} | required={allowed_roles}"
            )
            raise ForbiddenError("You do not have permission to perform this action.")

        return current_user

    return checker
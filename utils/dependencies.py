from typing import List

from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from utils.auth_utils import decode_access_token
from utils.constants import (
    AUTH_CREDENTIALS_MISSING,
    AUTH_ROLE_FORBIDDEN,
    AUTH_TOKEN_INVALID_OR_EXPIRED,
    AUTH_TOKEN_PAYLOAD_INVALID,
)
from utils.exceptions import UnauthorizedError, ForbiddenError
from utils.logger import logger

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security)
):
    if credentials is None:
        raise UnauthorizedError(AUTH_CREDENTIALS_MISSING)

    token = credentials.credentials

    payload = decode_access_token(token)

    if payload is None:
        raise UnauthorizedError(AUTH_TOKEN_INVALID_OR_EXPIRED)

    user_id = payload.get("user_id")
    email = payload.get("sub")
    role = payload.get("role")

    if user_id is None or email is None:
        logger.warning(f"Malformed JWT payload | payload={payload}")
        raise UnauthorizedError(AUTH_TOKEN_PAYLOAD_INVALID)

    return {
        "user_id": user_id,
        "email": email,
        "role": role
    }


def require_roles(allowed_roles: List[str]):

    async def checker(current_user=Depends(get_current_user)):

        if current_user["role"] not in allowed_roles:
            logger.warning(
                f"Permission denied | user={current_user['email']} "
                f"role={current_user['role']} | required={allowed_roles}"
            )
            raise ForbiddenError(AUTH_ROLE_FORBIDDEN)

        return current_user

    return checker

from typing import List

from fastapi import Depends, Path
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from utils.ci_client import validate_token, validate_case_access
from utils.constants import (
    AUTH_CREDENTIALS_MISSING,
    AUTH_ROLE_FORBIDDEN,
    CASE_ID_REQUIRED,
)
from utils.exceptions import UnauthorizedError, ForbiddenError, BadRequestError
from utils.logger import logger

security = HTTPBearer(auto_error=False)


async def authorize_case(access_token: str, case_id: int) -> dict:
    if case_id is None:
        raise BadRequestError(CASE_ID_REQUIRED)
    payload = await validate_token(access_token)
    case_data = await validate_case_access(access_token, case_id)
    ci_user = case_data.get("user", payload)

    return {
        "user_id": ci_user.get("user_id"),
        "email": ci_user.get("email"),
        "first_name": ci_user.get("first_name"),
        "last_name": ci_user.get("last_name"),
        "role": ci_user.get("role"),
        "case_id": case_id,
        "case": case_data.get("case"),
    }


def enforce_role(current_user: dict, allowed_roles: List[str]) -> dict:
    if current_user["role"] not in allowed_roles:
        logger.warning(
            f"Permission denied | user={current_user['email']} "
            f"role={current_user['role']} | required={allowed_roles}"
        )
        raise ForbiddenError(AUTH_ROLE_FORBIDDEN)
    return current_user


async def get_access_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> str:
    if credentials is None:
        raise UnauthorizedError(AUTH_CREDENTIALS_MISSING)
    return credentials.credentials


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security)
):
    if credentials is None:
        raise UnauthorizedError(AUTH_CREDENTIALS_MISSING)

    token = credentials.credentials

    payload = await validate_token(token)

    return {
        "user_id": payload.get("user_id"),
        "email": payload.get("email"),
        "first_name": payload.get("first_name"),
        "last_name": payload.get("last_name"),
        "role": payload.get("role"),
    }


async def get_current_case_context(
    case_id: int = Path(...),
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
):
    if credentials is None:
        raise UnauthorizedError(AUTH_CREDENTIALS_MISSING)

    return await authorize_case(credentials.credentials, case_id)


def require_roles(allowed_roles: List[str]):

    async def checker(current_user=Depends(get_current_user)):

        return enforce_role(current_user, allowed_roles)

    return checker


def require_roles_for_case(allowed_roles: List[str]):
    """
    Same role-gating as require_roles, but for case-scoped routes —
    validates against get_current_case_context (token + case access)
    instead of get_current_user (token only).
    """

    async def checker(current_user=Depends(get_current_case_context)):

        return enforce_role(current_user, allowed_roles)

    return checker
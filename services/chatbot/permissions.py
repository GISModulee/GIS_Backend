from __future__ import annotations

from utils.constants import AUTH_ROLE_FORBIDDEN
from utils.exceptions import ForbiddenError


def ensure_tool_permission(current_user: dict, allowed_roles: list[str] | None) -> None:
    if not allowed_roles:
        return
    if current_user.get("role") not in allowed_roles:
        raise ForbiddenError(AUTH_ROLE_FORBIDDEN)

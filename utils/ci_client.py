import httpx

from utils.config import settings
from utils.exceptions import UnauthorizedError, ForbiddenError
from utils.logger import logger


async def validate_token(access_token: str) -> dict:
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{settings.CI_BASE_URL}/auth/validate",
                params={"module_slug": settings.MODULE_SLUG},
                headers={"Authorization": f"Bearer {access_token}"},
            )
        except httpx.RequestError as e:
            logger.error(f"CI /auth/validate request failed | error={e}")
            raise UnauthorizedError("Unable to validate token with Central Intelligence")

    if resp.status_code != 200:
        logger.warning(f"CI token validation failed | status={resp.status_code}")
        raise UnauthorizedError("Invalid or unauthorized token")

    return resp.json()


async def validate_case_access(access_token: str, case_id: int) -> dict:
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{settings.CI_BASE_URL}/cases/{case_id}/validate",
                params={"module_slug": settings.MODULE_SLUG},
                headers={"Authorization": f"Bearer {access_token}"},
            )
        except httpx.RequestError as e:
            logger.error(f"CI case validate request failed | error={e}")
            raise ForbiddenError("Unable to validate case access with Central Intelligence")

    if resp.status_code != 200:
        logger.warning(f"CI case validation failed | status={resp.status_code} | case_id={case_id}")
        raise ForbiddenError("You dont have the required permissions to access this case")

    data = resp.json()
    if not data.get("valid"):
        logger.warning(f"User not authorized for case | case_id={case_id}")
        raise ForbiddenError("User not authorized for this case")

    return data


async def get_user_cases(access_token: str) -> list:
    """
    Fetch all cases assigned to the current user from Central Intelligence.
    Only cases the user has access to are returned.
    """
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{settings.CI_BASE_URL}/cases",
                params={"module_slug": settings.MODULE_SLUG},
                headers={"Authorization": f"Bearer {access_token}"},
            )
        except httpx.RequestError as e:
            logger.error(f"CI /cases request failed | error={e}")
            raise UnauthorizedError("Unable to fetch cases from Central Intelligence")

    if resp.status_code != 200:
        logger.warning(f"CI /cases request failed | status={resp.status_code}")
        raise UnauthorizedError("Failed to fetch cases from Central Intelligence")

    data = resp.json()
    cases = data.get("cases", []) if isinstance(data, dict) else data
    logger.info(f"Fetched {len(cases)} cases from CI")
    return cases
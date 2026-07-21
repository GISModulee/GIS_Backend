from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from utils.config import settings
from utils.logger import logger

# ===================================================
# PASSWORD HASHING
# ===================================================

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict) -> str:

    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )

    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )

    logger.info(f"JWT created | sub={data.get('sub')} | user_id={data.get('user_id')}")

    return encoded_jwt


def decode_access_token(token: str) -> dict | None:
    """
    Verifies signature + expiry.
    Returns the decoded payload dict if valid, otherwise None.
    Callers (see utils/dependencies.py) turn a None into a proper
    401 via UnauthorizedError — this function itself stays exception-free
    so it's easy to unit test / reuse outside a request context.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        return payload

    except jwt.ExpiredSignatureError:
        logger.warning("JWT rejected: expired token")
        return None

    except jwt.InvalidTokenError as e:
        logger.warning(f"JWT rejected: invalid token | error={e}")
        return None
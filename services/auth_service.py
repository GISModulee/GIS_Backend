from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from database.database import engine
from utils.auth_utils import hash_password, verify_password, create_access_token
from utils.logger import logger
from utils.exceptions import (
    BadRequestError,
    UnauthorizedError,
    ServiceUnavailableError,
)


def register_user(user):

    logger.info(f"Registration attempt | email={user.email} | role={user.role}")

    try:
        with engine.begin() as conn:

            existing = conn.execute(
                text("SELECT id FROM users WHERE email = :email"),
                {"email": user.email}
            ).fetchone()

            if existing:
                logger.warning(f"Registration rejected: email already registered | email={user.email}")
                raise BadRequestError("Email already registered")

            hashed_password = hash_password(user.password)
            username = user.email.split("@")[0]

            result = conn.execute(
                text("""
                    INSERT INTO users (username, email, password, full_name, role)
                    VALUES (:username, :email, :password, :full_name, :role)
                    RETURNING id, username, email, full_name, role, created_at, last_login
                """),
                {
                    "username": username,
                    "email": user.email,
                    "password": hashed_password,
                    "full_name": user.full_name,
                    "role": user.role.value
                }
            )

            new_user = result.fetchone()

    except BadRequestError:
        raise

    except SQLAlchemyError as e:
        logger.error(f"Registration failed | email={user.email} | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to register user") from e

    logger.info(f"User registered successfully | user_id={new_user.id} | email={new_user.email}")

    return {
        "success": True,
        "message": "User registered successfully",
        "user": {
            "id": new_user.id,
            "username": new_user.username,
            "email": new_user.email,
            "full_name": new_user.full_name,
            "role": new_user.role,
            "created_at": new_user.created_at,
            "last_login": new_user.last_login,
        }
    }


def login_user(user):

    logger.info(f"Login attempt | email={user.email}")

    try:
        with engine.begin() as conn:

            result = conn.execute(
                text("""
                    SELECT id, username, email, password, full_name, role, created_at, last_login
                    FROM users
                    WHERE email = :email
                """),
                {"email": user.email}
            )

            db_user = result.fetchone()

            if db_user is None:
                logger.warning(f"Failed login attempt: unknown email | email={user.email}")
                raise UnauthorizedError("Invalid email or password")

            if not verify_password(user.password, db_user.password):
                logger.warning(
                    f"Failed login attempt: bad password | user_id={db_user.id} | email={user.email}"
                )
                raise UnauthorizedError("Invalid email or password")

            updated = conn.execute(
                text("""
                    UPDATE users
                    SET last_login = NOW()
                    WHERE id = :id
                    RETURNING last_login
                """),
                {"id": db_user.id}
            ).fetchone()

    except UnauthorizedError:
        raise

    except SQLAlchemyError as e:
        logger.error(f"Login failed | email={user.email} | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to process login") from e

    logger.info(f"Login successful | user_id={db_user.id} | email={db_user.email} | role={db_user.role}")

    access_token = create_access_token(
        data={
            "sub": db_user.email,
            "user_id": db_user.id,
            "role": db_user.role
        }
    )

    return {
        "success": True,
        "message": "Login successful",
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": db_user.id,
            "username": db_user.username,
            "email": db_user.email,
            "full_name": db_user.full_name,
            "role": db_user.role,
            "created_at": db_user.created_at,
            "last_login": updated.last_login,
        }
    }

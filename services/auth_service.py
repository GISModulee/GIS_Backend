from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from models.model import User
from utils.auth_utils import hash_password, verify_password, create_access_token
from utils.logger import logger
from utils.exceptions import (
    ConflictError,
    UnauthorizedError,
    ServiceUnavailableError,
)


def register_user(user, db):
    logger.info(f"Registration attempt | email={user.email} | role={user.role}")

    try:
        existing = db.scalar(select(User.id).where(User.email == user.email))
        if existing is not None:
            logger.warning(
                f"Registration rejected: email already registered | email={user.email}"
            )
            raise ConflictError("Email already registered")

        new_user = User(
            username=user.email.split("@")[0],
            email=user.email,
            password=hash_password(user.password),
            full_name=user.full_name,
            role=user.role.value,
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        response_user = {
            "id": new_user.id,
            "username": new_user.username,
            "email": new_user.email,
            "full_name": new_user.full_name,
            "role": new_user.role,
            "created_at": new_user.created_at,
            "last_login": new_user.last_login,
        }

    except ConflictError:
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Registration failed | email={user.email} | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to register user") from e

    logger.info(
        f"User registered successfully | user_id={response_user['id']} | "
        f"email={response_user['email']}"
    )
    return {
        "success": True,
        "message": "User registered successfully",
        "user": response_user,
    }


def login_user(user, db):
    logger.info(f"Login attempt | email={user.email}")

    try:
        db_user = db.scalar(select(User).where(User.email == user.email))
        if db_user is None:
            logger.warning(f"Failed login attempt: unknown email | email={user.email}")
            raise UnauthorizedError("Invalid email or password")

        if not verify_password(user.password, db_user.password):
            logger.warning(
                f"Failed login attempt: bad password | user_id={db_user.id} | "
                f"email={user.email}"
            )
            raise UnauthorizedError("Invalid email or password")

        db_user.last_login = datetime.now()
        db.commit()
        db.refresh(db_user)
        response_user = {
            "id": db_user.id,
            "username": db_user.username,
            "email": db_user.email,
            "full_name": db_user.full_name,
            "role": db_user.role,
            "created_at": db_user.created_at,
            "last_login": db_user.last_login,
        }

    except UnauthorizedError:
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Login failed | email={user.email} | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to process login") from e

    logger.info(
        f"Login successful | user_id={response_user['id']} | "
        f"email={response_user['email']} | role={response_user['role']}"
    )
    access_token = create_access_token(
        data={
            "sub": response_user["email"],
            "user_id": response_user["id"],
            "role": response_user["role"],
        }
    )
    return {
        "success": True,
        "message": "Login successful",
        "access_token": access_token,
        "token_type": "bearer",
        "user": response_user,
    }

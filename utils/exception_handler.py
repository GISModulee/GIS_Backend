from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from utils.constants import (
    AUTH_SCHEME_BEARER,
    DETAIL_DATABASE_ERROR,
    DETAIL_UNEXPECTED_ERROR,
    DETAIL_VALIDATION_ERROR,
    HEADER_WWW_AUTHENTICATE,
    RESPONSE_DETAIL_KEY,
    RESPONSE_ERRORS_KEY,
    RESPONSE_REQUEST_ID_KEY,
    RESPONSE_STATUS_ERROR,
    RESPONSE_STATUS_KEY,
    STATUS_BAD_REQUEST,
    STATUS_INTERNAL_SERVER_ERROR,
    STATUS_SERVICE_UNAVAILABLE,
    STATUS_UNAUTHORIZED,
    STATUS_UNPROCESSABLE_ENTITY,
)
from utils.exceptions import AppException
from utils.logger import logger
from utils.request_context import get_request_id


async def _error_response(status_code: int, detail, errors=None, headers=None) -> JSONResponse:
    content = {
        RESPONSE_STATUS_KEY: RESPONSE_STATUS_ERROR,
        RESPONSE_DETAIL_KEY: detail,
        RESPONSE_REQUEST_ID_KEY: get_request_id(),
    }
    if errors is not None:
        content[RESPONSE_ERRORS_KEY] = errors
    headers = dict(headers or {})
    if status_code == STATUS_UNAUTHORIZED:
        headers.setdefault(HEADER_WWW_AUTHENTICATE, AUTH_SCHEME_BEARER)
    return JSONResponse(status_code=status_code, content=content, headers=headers)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        logger.warning(f"Validation error on {request.url.path}: {exc.errors()}")
        detail = DETAIL_VALIDATION_ERROR
        if request.url.path.startswith("/hotspots"):
            errors = exc.errors()
            if errors:
                detail = errors[0].get("msg", DETAIL_VALIDATION_ERROR)
                if isinstance(detail, str) and detail.startswith("Value error, "):
                    detail = detail.removeprefix("Value error, ")
        return await _error_response(
            STATUS_UNPROCESSABLE_ENTITY,
            detail,
            jsonable_encoder(exc.errors()),
        )

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        logger.warning(f"Application error on {request.url.path}: {exc.status_code} - {exc.detail}")
        return await _error_response(exc.status_code, exc.detail)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        logger.warning(f"HTTP error on {request.url.path}: {exc.status_code} - {exc.detail}")
        return await _error_response(exc.status_code, exc.detail, headers=exc.headers)

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
        logger.error(f"Database error on {request.url.path}: {exc}", exc_info=True)
        return await _error_response(STATUS_SERVICE_UNAVAILABLE, DETAIL_DATABASE_ERROR)

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        logger.warning(f"Value error on {request.url.path}: {exc}")
        return await _error_response(STATUS_BAD_REQUEST, str(exc))

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception on {request.url.path}: {exc}", exc_info=True)
        return await _error_response(STATUS_INTERNAL_SERVER_ERROR, DETAIL_UNEXPECTED_ERROR)

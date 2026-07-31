from fastapi import FastAPI, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from utils.constants import (
    DETAIL_DATABASE_ERROR,
    DETAIL_UNEXPECTED_ERROR,
    DETAIL_VALIDATION_ERROR,
)
from utils.exceptions import AppException
from utils.logger import logger
from utils.request_context import get_request_id


def _error_response(status_code: int, detail, errors=None, headers=None) -> JSONResponse:
    content = {
        "status": "error",
        "detail": detail,
        "request_id": get_request_id(),
    }
    if errors is not None:
        content["errors"] = errors
    headers = dict(headers or {})
    if status_code == status.HTTP_401_UNAUTHORIZED:
        headers.setdefault("WWW-Authenticate", "Bearer")
    return JSONResponse(status_code=status_code, content=content, headers=headers)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        logger.warning(f"Validation error on {request.url.path}: {exc.errors()}")
        return _error_response(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            DETAIL_VALIDATION_ERROR,
            jsonable_encoder(exc.errors()),
        )

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        logger.warning(f"Application error on {request.url.path}: {exc.status_code} - {exc.detail}")
        return _error_response(exc.status_code, exc.detail)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        logger.warning(f"HTTP error on {request.url.path}: {exc.status_code} - {exc.detail}")
        return _error_response(exc.status_code, exc.detail, headers=exc.headers)

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
        logger.error(f"Database error on {request.url.path}: {exc}", exc_info=True)
        return _error_response(status.HTTP_503_SERVICE_UNAVAILABLE, DETAIL_DATABASE_ERROR)

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        logger.warning(f"Value error on {request.url.path}: {exc}")
        return _error_response(status.HTTP_400_BAD_REQUEST, str(exc))

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception on {request.url.path}: {exc}", exc_info=True)
        return _error_response(status.HTTP_500_INTERNAL_SERVER_ERROR, DETAIL_UNEXPECTED_ERROR)

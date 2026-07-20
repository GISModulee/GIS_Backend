from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy.exc import SQLAlchemyError

from utils.logger import logger
from utils.request_context import get_request_id


class AppException(Exception):

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class NotFoundError(AppException):
    def __init__(self, detail: str = "Resource not found"):
        super().__init__(status_code=404, detail=detail)


class BadRequestError(AppException):
    def __init__(self, detail: str = "Invalid request"):
        super().__init__(status_code=400, detail=detail)


class UnauthorizedError(AppException):
    """401 - missing / invalid / expired credentials."""
    def __init__(self, detail: str = "Not authenticated"):
        super().__init__(status_code=401, detail=detail)


class ForbiddenError(AppException):
    """403 - authenticated, but not allowed to do this (role check failed)."""
    def __init__(self, detail: str = "Permission denied"):
        super().__init__(status_code=403, detail=detail)


class UnsupportedMediaTypeError(AppException):
    def __init__(self, detail: str = "Unsupported media type"):
        super().__init__(status_code=415, detail=detail)


class PayloadTooLargeError(AppException):
    def __init__(self, detail: str = "Payload too large"):
        super().__init__(status_code=413, detail=detail)


class UnprocessableEntityError(AppException):
    def __init__(self, detail: str = "Unprocessable entity"):
        super().__init__(status_code=422, detail=detail)


class ServiceUnavailableError(AppException):
    def __init__(self, detail: str = "Service unavailable"):
        super().__init__(status_code=503, detail=detail)


# ===================================================
# HELPERS
# ===================================================
def _error_response(status_code: int, detail, errors=None) -> JSONResponse:
    content = {
        "status": "error",
        "detail": detail,
        "request_id": get_request_id(),
    }
    if errors is not None:
        content["errors"] = errors

    headers = None
    # Per RFC 7235, a 401 response should carry a WWW-Authenticate header.
    # FastAPI's own HTTPException(401) does this for OAuth2PasswordBearer;
    # we replicate it here so our custom UnauthorizedError behaves the same.
    if status_code == 401:
        headers = {"WWW-Authenticate": "Bearer"}

    return JSONResponse(status_code=status_code, content=content, headers=headers)


# ===================================================
# REGISTRATION
# ===================================================
def register_exception_handlers(app: FastAPI) -> None:
    """Attach every exception handler to the FastAPI app. Call once from main.py."""

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        logger.warning(f"Validation error on {request.url.path}: {exc.errors()}")
        return _error_response(
            status_code=422,
            detail="Invalid request data.",
            errors=jsonable_encoder(exc.errors()),
        )

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        logger.warning(f"AppException on {request.url.path}: {exc.status_code} - {exc.detail}")
        return _error_response(status_code=exc.status_code, detail=exc.detail)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        logger.warning(f"HTTPException on {request.url.path}: {exc.status_code} - {exc.detail}")
        return _error_response(status_code=exc.status_code, detail=exc.detail)

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
        logger.error(f"Database error on {request.url.path}: {exc}", exc_info=True)
        return _error_response(
            status_code=503,
            detail="A database error occurred. Please try again later.",
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        logger.warning(f"Value error on {request.url.path}: {exc}")
        return _error_response(status_code=400, detail=str(exc))

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception on {request.url.path}: {exc}", exc_info=True)
        return _error_response(
            status_code=500,
            detail="An unexpected error occurred. Please try again or contact support.",
        )
    
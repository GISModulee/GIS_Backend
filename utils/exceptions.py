from fastapi import status

from utils.constants import (
    DETAIL_BAD_GATEWAY,
    DETAIL_BAD_REQUEST,
    DETAIL_CONFLICT,
    DETAIL_FORBIDDEN,
    DETAIL_GATEWAY_TIMEOUT,
    DETAIL_GONE,
    DETAIL_INTERNAL_SERVER_ERROR,
    DETAIL_METHOD_NOT_ALLOWED,
    DETAIL_NOT_FOUND,
    DETAIL_NOT_IMPLEMENTED,
    DETAIL_PAYLOAD_TOO_LARGE,
    DETAIL_REQUEST_TIMEOUT,
    DETAIL_SERVICE_UNAVAILABLE,
    DETAIL_TOO_MANY_REQUESTS,
    DETAIL_UNAUTHORIZED,
    DETAIL_UNPROCESSABLE_ENTITY,
    DETAIL_UNSUPPORTED_MEDIA_TYPE,
)


class AppException(Exception):
    """Base class for expected application errors exposed by the API."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class BadRequestError(AppException):
    def __init__(self, detail: str = DETAIL_BAD_REQUEST):
        super().__init__(status.HTTP_400_BAD_REQUEST, detail)


class UnauthorizedError(AppException):
    def __init__(self, detail: str = DETAIL_UNAUTHORIZED):
        super().__init__(status.HTTP_401_UNAUTHORIZED, detail)


class ForbiddenError(AppException):
    def __init__(self, detail: str = DETAIL_FORBIDDEN):
        super().__init__(status.HTTP_403_FORBIDDEN, detail)


class NotFoundError(AppException):
    def __init__(self, detail: str = DETAIL_NOT_FOUND):
        super().__init__(status.HTTP_404_NOT_FOUND, detail)


class MethodNotAllowedError(AppException):
    def __init__(self, detail: str = DETAIL_METHOD_NOT_ALLOWED):
        super().__init__(status.HTTP_405_METHOD_NOT_ALLOWED, detail)


class RequestTimeoutError(AppException):
    def __init__(self, detail: str = DETAIL_REQUEST_TIMEOUT):
        super().__init__(status.HTTP_408_REQUEST_TIMEOUT, detail)


class ConflictError(AppException):
    def __init__(self, detail: str = DETAIL_CONFLICT):
        super().__init__(status.HTTP_409_CONFLICT, detail)


class GoneError(AppException):
    def __init__(self, detail: str = DETAIL_GONE):
        super().__init__(status.HTTP_410_GONE, detail)


class PayloadTooLargeError(AppException):
    def __init__(self, detail: str = DETAIL_PAYLOAD_TOO_LARGE):
        super().__init__(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail)


class UnsupportedMediaTypeError(AppException):
    def __init__(self, detail: str = DETAIL_UNSUPPORTED_MEDIA_TYPE):
        super().__init__(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail)


class UnprocessableEntityError(AppException):
    def __init__(self, detail: str = DETAIL_UNPROCESSABLE_ENTITY):
        super().__init__(status.HTTP_422_UNPROCESSABLE_ENTITY, detail)


class TooManyRequestsError(AppException):
    def __init__(self, detail: str = DETAIL_TOO_MANY_REQUESTS):
        super().__init__(status.HTTP_429_TOO_MANY_REQUESTS, detail)


class InternalServerError(AppException):
    def __init__(self, detail: str = DETAIL_INTERNAL_SERVER_ERROR):
        super().__init__(status.HTTP_500_INTERNAL_SERVER_ERROR, detail)


class NotImplementedError_(AppException):
    def __init__(self, detail: str = DETAIL_NOT_IMPLEMENTED):
        super().__init__(status.HTTP_501_NOT_IMPLEMENTED, detail)


class BadGatewayError(AppException):
    def __init__(self, detail: str = DETAIL_BAD_GATEWAY):
        super().__init__(status.HTTP_502_BAD_GATEWAY, detail)


class ServiceUnavailableError(AppException):
    def __init__(self, detail: str = DETAIL_SERVICE_UNAVAILABLE):
        super().__init__(status.HTTP_503_SERVICE_UNAVAILABLE, detail)


class GatewayTimeoutError(AppException):
    def __init__(self, detail: str = DETAIL_GATEWAY_TIMEOUT):
        super().__init__(status.HTTP_504_GATEWAY_TIMEOUT, detail)

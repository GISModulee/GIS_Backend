from utils.constants import (
    DETAIL_BAD_REQUEST,
    DETAIL_CONFLICT,
    DETAIL_FORBIDDEN,
    DETAIL_GATEWAY_TIMEOUT,
    DETAIL_NOT_FOUND,
    DETAIL_NOT_IMPLEMENTED,
    DETAIL_PAYLOAD_TOO_LARGE,
    DETAIL_SERVICE_UNAVAILABLE,
    DETAIL_UNAUTHORIZED,
    DETAIL_UNPROCESSABLE_ENTITY,
    DETAIL_UNSUPPORTED_MEDIA_TYPE,
    STATUS_BAD_REQUEST,
    STATUS_CONFLICT,
    STATUS_FORBIDDEN,
    STATUS_GATEWAY_TIMEOUT,
    STATUS_NOT_FOUND,
    STATUS_NOT_IMPLEMENTED,
    STATUS_PAYLOAD_TOO_LARGE,
    STATUS_SERVICE_UNAVAILABLE,
    STATUS_UNAUTHORIZED,
    STATUS_UNPROCESSABLE_ENTITY,
    STATUS_UNSUPPORTED_MEDIA_TYPE,
)


class AppException(Exception):
    """Base class for expected application errors exposed by the API."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class BadRequestError(AppException):
    def __init__(self, detail: str = DETAIL_BAD_REQUEST):
        super().__init__(STATUS_BAD_REQUEST, detail)


class UnauthorizedError(AppException):
    def __init__(self, detail: str = DETAIL_UNAUTHORIZED):
        super().__init__(STATUS_UNAUTHORIZED, detail)


class ForbiddenError(AppException):
    def __init__(self, detail: str = DETAIL_FORBIDDEN):
        super().__init__(STATUS_FORBIDDEN, detail)


class NotFoundError(AppException):
    def __init__(self, detail: str = DETAIL_NOT_FOUND):
        super().__init__(STATUS_NOT_FOUND, detail)


class ConflictError(AppException):
    def __init__(self, detail: str = DETAIL_CONFLICT):
        super().__init__(STATUS_CONFLICT, detail)


class PayloadTooLargeError(AppException):
    def __init__(self, detail: str = DETAIL_PAYLOAD_TOO_LARGE):
        super().__init__(STATUS_PAYLOAD_TOO_LARGE, detail)


class UnsupportedMediaTypeError(AppException):
    def __init__(self, detail: str = DETAIL_UNSUPPORTED_MEDIA_TYPE):
        super().__init__(STATUS_UNSUPPORTED_MEDIA_TYPE, detail)


class UnprocessableEntityError(AppException):
    def __init__(self, detail: str = DETAIL_UNPROCESSABLE_ENTITY):
        super().__init__(STATUS_UNPROCESSABLE_ENTITY, detail)


class NotImplementedError_(AppException):
    def __init__(self, detail: str = DETAIL_NOT_IMPLEMENTED):
        super().__init__(STATUS_NOT_IMPLEMENTED, detail)


class ServiceUnavailableError(AppException):
    def __init__(self, detail: str = DETAIL_SERVICE_UNAVAILABLE):
        super().__init__(STATUS_SERVICE_UNAVAILABLE, detail)


class GatewayTimeoutError(AppException):
    def __init__(self, detail: str = DETAIL_GATEWAY_TIMEOUT):
        super().__init__(STATUS_GATEWAY_TIMEOUT, detail)

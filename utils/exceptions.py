from utils.constants import (
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    HTTP_405_METHOD_NOT_ALLOWED,
    HTTP_408_REQUEST_TIMEOUT,
    HTTP_409_CONFLICT,
    HTTP_410_GONE,
    HTTP_413_PAYLOAD_TOO_LARGE,
    HTTP_415_UNSUPPORTED_MEDIA_TYPE,
    HTTP_422_UNPROCESSABLE_ENTITY,
    HTTP_429_TOO_MANY_REQUESTS,
    HTTP_500_INTERNAL_SERVER_ERROR,
    HTTP_501_NOT_IMPLEMENTED,
    HTTP_502_BAD_GATEWAY,
    HTTP_503_SERVICE_UNAVAILABLE,
    HTTP_504_GATEWAY_TIMEOUT,
    DETAIL_BAD_REQUEST,
    DETAIL_UNAUTHORIZED,
    DETAIL_FORBIDDEN,
    DETAIL_NOT_FOUND,
    DETAIL_METHOD_NOT_ALLOWED,
    DETAIL_REQUEST_TIMEOUT,
    DETAIL_CONFLICT,
    DETAIL_GONE,
    DETAIL_PAYLOAD_TOO_LARGE,
    DETAIL_UNSUPPORTED_MEDIA_TYPE,
    DETAIL_UNPROCESSABLE_ENTITY,
    DETAIL_TOO_MANY_REQUESTS,
    DETAIL_INTERNAL_SERVER_ERROR,
    DETAIL_NOT_IMPLEMENTED,
    DETAIL_BAD_GATEWAY,
    DETAIL_SERVICE_UNAVAILABLE,
    DETAIL_GATEWAY_TIMEOUT,
)
 
 
class AppException(Exception):
 
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)
 
 
# ===================================================
# 4xx CLIENT ERRORS
# ===================================================
 
class BadRequestError(AppException):
    def __init__(self, detail: str = DETAIL_BAD_REQUEST):
        super().__init__(status_code=HTTP_400_BAD_REQUEST, detail=detail)
 
 
class UnauthorizedError(AppException):
    def __init__(self, detail: str = DETAIL_UNAUTHORIZED):
        super().__init__(status_code=HTTP_401_UNAUTHORIZED, detail=detail)
 
 
class ForbiddenError(AppException):
    def __init__(self, detail: str = DETAIL_FORBIDDEN):
        super().__init__(status_code=HTTP_403_FORBIDDEN, detail=detail)
 
 
class NotFoundError(AppException):
    def __init__(self, detail: str = DETAIL_NOT_FOUND):
        super().__init__(status_code=HTTP_404_NOT_FOUND, detail=detail)
 
 
class MethodNotAllowedError(AppException):
    def __init__(self, detail: str = DETAIL_METHOD_NOT_ALLOWED):
        super().__init__(status_code=HTTP_405_METHOD_NOT_ALLOWED, detail=detail)
 
 
class RequestTimeoutError(AppException):
    def __init__(self, detail: str = DETAIL_REQUEST_TIMEOUT):
        super().__init__(status_code=HTTP_408_REQUEST_TIMEOUT, detail=detail)
 
 
class ConflictError(AppException):
    def __init__(self, detail: str = DETAIL_CONFLICT):
        super().__init__(status_code=HTTP_409_CONFLICT, detail=detail)
 
 
class GoneError(AppException):
    def __init__(self, detail: str = DETAIL_GONE):
        super().__init__(status_code=HTTP_410_GONE, detail=detail)
 
 
class PayloadTooLargeError(AppException):
    def __init__(self, detail: str = DETAIL_PAYLOAD_TOO_LARGE):
        super().__init__(status_code=HTTP_413_PAYLOAD_TOO_LARGE, detail=detail)
 
 
class UnsupportedMediaTypeError(AppException):
    def __init__(self, detail: str = DETAIL_UNSUPPORTED_MEDIA_TYPE):
        super().__init__(status_code=HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=detail)
 
 
class UnprocessableEntityError(AppException):
    def __init__(self, detail: str = DETAIL_UNPROCESSABLE_ENTITY):
        super().__init__(status_code=HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)
 
 
class TooManyRequestsError(AppException):
    def __init__(self, detail: str = DETAIL_TOO_MANY_REQUESTS):
        super().__init__(status_code=HTTP_429_TOO_MANY_REQUESTS, detail=detail)
 
 
# ===================================================
# 5xx SERVER ERRORS
# ===================================================
 
class InternalServerError(AppException):
    def __init__(self, detail: str = DETAIL_INTERNAL_SERVER_ERROR):
        super().__init__(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail=detail)
 
 
class NotImplementedError_(AppException):
    # Named with a trailing underscore to avoid shadowing Python's
    # built-in NotImplementedError.
    def __init__(self, detail: str = DETAIL_NOT_IMPLEMENTED):
        super().__init__(status_code=HTTP_501_NOT_IMPLEMENTED, detail=detail)
 
 
class BadGatewayError(AppException):
    def __init__(self, detail: str = DETAIL_BAD_GATEWAY):
        super().__init__(status_code=HTTP_502_BAD_GATEWAY, detail=detail)
 
 
class ServiceUnavailableError(AppException):
    def __init__(self, detail: str = DETAIL_SERVICE_UNAVAILABLE):
        super().__init__(status_code=HTTP_503_SERVICE_UNAVAILABLE, detail=detail)
 
 
class GatewayTimeoutError(AppException):
    def __init__(self, detail: str = DETAIL_GATEWAY_TIMEOUT):
        super().__init__(status_code=HTTP_504_GATEWAY_TIMEOUT, detail=detail)
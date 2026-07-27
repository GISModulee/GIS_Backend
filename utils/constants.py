
HTTP_400_BAD_REQUEST = 400
HTTP_401_UNAUTHORIZED = 401
HTTP_402_PAYMENT_REQUIRED = 402
HTTP_403_FORBIDDEN = 403
HTTP_404_NOT_FOUND = 404
HTTP_405_METHOD_NOT_ALLOWED = 405
HTTP_406_NOT_ACCEPTABLE = 406
HTTP_407_PROXY_AUTHENTICATION_REQUIRED = 407
HTTP_408_REQUEST_TIMEOUT = 408
HTTP_409_CONFLICT = 409
HTTP_410_GONE = 410
HTTP_411_LENGTH_REQUIRED = 411
HTTP_412_PRECONDITION_FAILED = 412
HTTP_413_PAYLOAD_TOO_LARGE = 413
HTTP_414_URI_TOO_LONG = 414
HTTP_415_UNSUPPORTED_MEDIA_TYPE = 415
HTTP_416_RANGE_NOT_SATISFIABLE = 416
HTTP_417_EXPECTATION_FAILED = 417
HTTP_418_IM_A_TEAPOT = 418
HTTP_421_MISDIRECTED_REQUEST = 421
HTTP_422_UNPROCESSABLE_ENTITY = 422
HTTP_423_LOCKED = 423
HTTP_424_FAILED_DEPENDENCY = 424
HTTP_425_TOO_EARLY = 425
HTTP_426_UPGRADE_REQUIRED = 426
HTTP_428_PRECONDITION_REQUIRED = 428
HTTP_429_TOO_MANY_REQUESTS = 429
HTTP_431_REQUEST_HEADER_FIELDS_TOO_LARGE = 431
HTTP_451_UNAVAILABLE_FOR_LEGAL_REASONS = 451
 
 
# ===================================================
# HTTP STATUS CODES — 5xx SERVER ERRORS
# ===================================================
 
HTTP_500_INTERNAL_SERVER_ERROR = 500
HTTP_501_NOT_IMPLEMENTED = 501
HTTP_502_BAD_GATEWAY = 502
HTTP_503_SERVICE_UNAVAILABLE = 503
HTTP_504_GATEWAY_TIMEOUT = 504
HTTP_505_HTTP_VERSION_NOT_SUPPORTED = 505
HTTP_506_VARIANT_ALSO_NEGOTIATES = 506
HTTP_507_INSUFFICIENT_STORAGE = 507
HTTP_508_LOOP_DETECTED = 508
HTTP_510_NOT_EXTENDED = 510
HTTP_511_NETWORK_AUTHENTICATION_REQUIRED = 511
 
 
# ===================================================
# DEFAULT ERROR DETAIL MESSAGES — 4xx
# ===================================================
# Default `detail` text for each status, used when the raising code
# doesn't supply a more specific message.
 
DETAIL_BAD_REQUEST = "Invalid request"
DETAIL_UNAUTHORIZED = "Not authenticated"
DETAIL_PAYMENT_REQUIRED = "Payment required"
DETAIL_FORBIDDEN = "Permission denied"
DETAIL_NOT_FOUND = "Resource not found"
DETAIL_METHOD_NOT_ALLOWED = "Method not allowed"
DETAIL_NOT_ACCEPTABLE = "Not acceptable"
DETAIL_PROXY_AUTHENTICATION_REQUIRED = "Proxy authentication required"
DETAIL_REQUEST_TIMEOUT = "Request timeout"
DETAIL_CONFLICT = "Conflict with current state of the resource"
DETAIL_GONE = "Resource no longer available"
DETAIL_LENGTH_REQUIRED = "Length required"
DETAIL_PRECONDITION_FAILED = "Precondition failed"
DETAIL_PAYLOAD_TOO_LARGE = "Payload too large"
DETAIL_URI_TOO_LONG = "URI too long"
DETAIL_UNSUPPORTED_MEDIA_TYPE = "Unsupported media type"
DETAIL_RANGE_NOT_SATISFIABLE = "Range not satisfiable"
DETAIL_EXPECTATION_FAILED = "Expectation failed"
DETAIL_IM_A_TEAPOT = "I'm a teapot"
DETAIL_MISDIRECTED_REQUEST = "Misdirected request"
DETAIL_UNPROCESSABLE_ENTITY = "Unprocessable entity"
DETAIL_LOCKED = "Resource is locked"
DETAIL_FAILED_DEPENDENCY = "Failed dependency"
DETAIL_TOO_EARLY = "Too early"
DETAIL_UPGRADE_REQUIRED = "Upgrade required"
DETAIL_PRECONDITION_REQUIRED = "Precondition required"
DETAIL_TOO_MANY_REQUESTS = "Too many requests"
DETAIL_REQUEST_HEADER_FIELDS_TOO_LARGE = "Request header fields too large"
DETAIL_UNAVAILABLE_FOR_LEGAL_REASONS = "Unavailable for legal reasons"
 
 
# ===================================================
# DEFAULT ERROR DETAIL MESSAGES — 5xx
# ===================================================
 
DETAIL_INTERNAL_SERVER_ERROR = "An unexpected error occurred. Please try again or contact support."
DETAIL_NOT_IMPLEMENTED = "Not implemented"
DETAIL_BAD_GATEWAY = "Bad gateway"
DETAIL_SERVICE_UNAVAILABLE = "Service unavailable"
DETAIL_GATEWAY_TIMEOUT = "Gateway timeout"
DETAIL_HTTP_VERSION_NOT_SUPPORTED = "HTTP version not supported"
DETAIL_VARIANT_ALSO_NEGOTIATES = "Variant also negotiates"
DETAIL_INSUFFICIENT_STORAGE = "Insufficient storage"
DETAIL_LOOP_DETECTED = "Loop detected"
DETAIL_NOT_EXTENDED = "Not extended"
DETAIL_NETWORK_AUTHENTICATION_REQUIRED = "Network authentication required"
 
 
# ===================================================
# GLOBAL / FALLBACK HANDLER MESSAGES
# ===================================================
# Used directly by the generic handlers in exception_handler.py
# (RequestValidationError, SQLAlchemyError, bare Exception, etc.)
# where there is no AppException subclass involved.
 
DETAIL_VALIDATION_ERROR = "Invalid request data."
DETAIL_DATABASE_ERROR = "A database error occurred. Please try again later."
DETAIL_UNEXPECTED_ERROR = "An unexpected error occurred. Please try again or contact support."
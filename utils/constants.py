DETAIL_BAD_REQUEST = "Invalid request"
DETAIL_UNAUTHORIZED = "Not authenticated"
DETAIL_FORBIDDEN = "Permission denied"
DETAIL_NOT_FOUND = "Resource not found"
DETAIL_METHOD_NOT_ALLOWED = "Method not allowed"
DETAIL_REQUEST_TIMEOUT = "Request timeout"
DETAIL_CONFLICT = "Conflict with current state of the resource"
DETAIL_GONE = "Resource no longer available"
DETAIL_PAYLOAD_TOO_LARGE = "Payload too large"
DETAIL_UNSUPPORTED_MEDIA_TYPE = "Unsupported media type"
DETAIL_UNPROCESSABLE_ENTITY = "Unprocessable entity"
DETAIL_TOO_MANY_REQUESTS = "Too many requests"

DETAIL_INTERNAL_SERVER_ERROR = "An unexpected error occurred. Please try again or contact support."
DETAIL_NOT_IMPLEMENTED = "Not implemented"
DETAIL_BAD_GATEWAY = "Bad gateway"
DETAIL_SERVICE_UNAVAILABLE = "Service unavailable"
DETAIL_GATEWAY_TIMEOUT = "Gateway timeout"

DETAIL_VALIDATION_ERROR = "Invalid request data."
DETAIL_DATABASE_ERROR = "A database error occurred. Please try again later."
DETAIL_UNEXPECTED_ERROR = "An unexpected error occurred. Please try again or contact support."

GEO_SEARCH_STATUS_SUCCESS = "success"
GEO_SEARCH_STATUS_PARTIAL_SUCCESS = "partial_success"
GEO_SEARCH_STATUS_UPSTREAM_UNAVAILABLE = "upstream_unavailable"
GEO_SEARCH_PROVIDER_EMPTY = "empty"
GEO_SEARCH_PROVIDER_TIMEOUT = "timeout"
GEO_SEARCH_PROVIDER_RATE_LIMITED = "rate_limited"
GEO_SEARCH_PROVIDER_ERROR = "error"

GEO_SEARCH_FEATURE_LOAD_FAILED = "Failed to load selected feature"
GEO_SEARCH_FEATURE_NOT_FOUND = "Feature not found for selected case and layer"
GEO_SEARCH_FEATURE_EMPTY_GEOMETRY = "Selected feature has no geometry"
GEO_SEARCH_FEATURE_INVALID_GEOMETRY = "Selected feature has invalid geometry"
GEO_SEARCH_FEATURE_EMPTY_SHAPE = "Selected feature has an empty geometry"
GEO_SEARCH_FEATURE_BOUNDS_INVALID = (
    "Selected feature geometry is outside valid longitude/latitude bounds"
)
GEO_SEARCH_AREA_TOO_LARGE = "Search area is too large; submit a smaller geometry."
GEO_SEARCH_TIMEOUT = (
    "News search timed out before results could be retrieved. Please try again."
)
GEO_SEARCH_NO_RESULTS = (
    "No matching news was found for the selected area and filters."
)
GEO_SEARCH_PROVIDERS_UNAVAILABLE = (
    "News providers are temporarily unavailable. Please try again."
)
GEO_SEARCH_BATCHES_PARTIAL = "Some place batches failed"
GEO_SEARCH_BATCHES_FAILED = "All place batches failed"
GEO_SEARCH_GDELT_FAILED = "GDELT connection failed on HTTPS and HTTP endpoints"
GEO_SEARCH_GDELT_RATE_LIMITED = "GDELT allows one request every five seconds"
GEO_SEARCH_GOVERNMENT_TIMEOUT = "Government search timed out"

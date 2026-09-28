from typing import Literal, get_args

STATUS_OK = 200
STATUS_BAD_REQUEST = 400
STATUS_UNAUTHORIZED = 401
STATUS_FORBIDDEN = 403
STATUS_NOT_FOUND = 404
STATUS_METHOD_NOT_ALLOWED = 405
STATUS_REQUEST_TIMEOUT = 408
STATUS_CONFLICT = 409
STATUS_GONE = 410
STATUS_PAYLOAD_TOO_LARGE = 413
STATUS_UNSUPPORTED_MEDIA_TYPE = 415
STATUS_UNPROCESSABLE_ENTITY = 422
STATUS_TOO_MANY_REQUESTS = 429
STATUS_INTERNAL_SERVER_ERROR = 500
STATUS_NOT_IMPLEMENTED = 501
STATUS_BAD_GATEWAY = 502
STATUS_SERVICE_UNAVAILABLE = 503
STATUS_GATEWAY_TIMEOUT = 504
 
RESPONSE_STATUS_KEY = "status"
RESPONSE_DETAIL_KEY = "detail"
RESPONSE_REQUEST_ID_KEY = "request_id"
RESPONSE_ERRORS_KEY = "errors"
RESPONSE_STATUS_ERROR = "error"
HEADER_WWW_AUTHENTICATE = "WWW-Authenticate"
AUTH_SCHEME_BEARER = "Bearer"
 
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
 
AUTH_CREDENTIALS_MISSING = "Authentication credentials were not provided."
AUTH_ROLE_FORBIDDEN = "You do not have permission to perform this action."

# ===================================================
# MODULE SLUGS
# ===================================================
# Identifies which source module a layer/feature originated from.
# This is separate from settings.MODULE_SLUG (the CI authentication
# module), which is defined in utils/config.py and used by the CI
# client. Slugs here are data-origin metadata, never auth metadata.
DEFAULT_MODULE_SLUG = "gis"
EMAIL_DUMP_MODULE_SLUG = "email-dump"
TELECOM_ANALYSIS_MODULE_SLUG = "telecom-analysis"

ALLOWED_MODULE_SLUGS = frozenset({
    DEFAULT_MODULE_SLUG,
    EMAIL_DUMP_MODULE_SLUG,
    TELECOM_ANALYSIS_MODULE_SLUG,
})

MAX_MODULE_SLUG_LENGTH = 80

# Fine-grained module_slug validation errors, surfaced to API clients
# so each failure mode returns a specific message.
MODULE_SLUG_REQUIRED = "module_slug is required"
MODULE_SLUG_EMPTY = "module_slug must not be empty or whitespace-only"
MODULE_SLUG_TOO_LONG = (
    f"module_slug must not exceed {MAX_MODULE_SLUG_LENGTH} characters"
)
MODULE_SLUG_NOT_FOUND = "Module slug not found"
MODULE_SLUG_INVALID = "Invalid module slug"
 
CASE_NOT_FOUND = "Case not found"
CASE_ID_REQUIRED = "case_id is required"
CASE_CREATE_FAILED = "Failed to create case"
CASE_FETCH_FAILED = "Failed to fetch case"
CASES_FETCH_FAILED = "Failed to fetch cases"
CASE_UPDATE_FAILED = "Failed to update case"
CASE_DELETE_FAILED = "Failed to delete case"
 
LAYER_NOT_FOUND = "Layer not found"
LAYER_CREATE_FAILED = "Failed to create layer"
LAYER_FETCH_FAILED = "Failed to fetch layer"
LAYER_UPDATE_FAILED = "Failed to update layer"
LAYER_DELETE_FAILED = "Failed to delete layer"
LAYER_AUTO_CREATE_FAILED = "Failed to auto-create layer"
LAYER_DUPLICATE_IMPORT_CHECK_FAILED = "Failed to check for duplicate import"
LAYER_DUPLICATE_NAME_TEMPLATE = "A layer named '{name}' already exists in this case. {suffix}"
LAYER_DUPLICATE_SUFFIX_DEFAULT = "Choose a different name."
LAYER_DUPLICATE_SUFFIX_IMPORT = "Pass a different 'layer_name' on the import request to disambiguate."
LAYER_CREATE_CASE_NOT_FOUND_TEMPLATE = "Cannot create layer: case_id {case_id} does not exist."
 
FEATURE_NOT_FOUND = "Feature not found"
FEATURE_CREATE_FAILED = "Failed to create feature"
FEATURE_CREATE_CONSTRAINT_FAILED = "Feature creation failed due to database constraint"
FEATURE_FETCH_FAILED = "Failed to fetch feature"
FEATURES_FETCH_FAILED = "Failed to fetch features"
FEATURE_UPDATE_FAILED = "Failed to update feature"
FEATURE_DELETE_FAILED = "Failed to delete feature"
FEATURE_LAYER_DOES_NOT_EXIST = "The specified layer does not exist"
FEATURE_LAYER_CASE_MISMATCH = "Layer does not belong to the specified case."
FEATURE_GEOMETRY_REQUIRED = "'geometry' is required for this geometry_type"
FEATURE_CIRCLE_CENTER_REQUIRED = "Circle features require a 'center' with lat/lng"
FEATURE_CIRCLE_RADIUS_REQUIRED = "Circle features require a 'radius'"
FEATURE_INVALID_GEOMETRY = "Invalid geometry data"
FEATURE_NUMBERS_VERIFY_FAILED = "Failed to verify features"
FEATURE_NUMBERS_NOT_FOUND_TEMPLATE = "Feature number(s) not found: {missing}"
 
COMMENT_NOT_FOUND = "Comment not found"
COMMENT_ATTACHMENT_NOT_FOUND = "No attachment found"
COMMENT_CREATE_FAILED = "Failed to create comment"
COMMENT_FETCH_FAILED = "Failed to fetch comments"
COMMENT_DELETE_FAILED = "Failed to delete comment"
COMMENT_ATTACHMENT_FETCH_FAILED = "Failed to fetch comment attachment"
 
IMAGE_NOT_FOUND = "Image not found"
IMAGE_READ_FAILED = "Unable to read uploaded file"
GEOCLIP_PREDICTION_FAILED = "GeoCLIP prediction failed"
GEOCLIP_NO_PREDICTIONS = "No location predictions could be generated for this image."
GEOCLIP_TOP_K_RANGE_TEMPLATE = "top_k must be between {min_top_k} and {max_top_k} (got {top_k})."
GEOCLIP_MODEL_INIT_FAILED = "GeoCLIP model initialization failed."
GEOCLIP_MODEL_NOT_LOADED = "GeoCLIP model is not loaded. Ensure load_model() is called at startup."
GEOCLIP_MODEL_INFERENCE_FAILED = "GeoCLIP inference failed."
DATABASE_SAVE_FAILED = "Database save failed"
 
FILE_NAME_MISSING = "Filename is missing."
FILE_NAME_INVALID = "Invalid filename"
FILE_EMPTY = "Uploaded file is empty."
FILE_TOO_LARGE_TEMPLATE = "File too large. Maximum allowed size is {max_mb} MB."
FILE_TYPE_UNSUPPORTED = "Unsupported media type"
FILE_TYPE_DETECTION_FAILED = "Unable to determine file type from content."
FILE_IMAGE_CONTENT_TYPE_UNSUPPORTED_TEMPLATE = (
    "File content is '{detected_mime}', which is not an allowed image type. "
    "Rename attacks (e.g. .docx -> .jpg) are rejected."
)
UPLOAD_TYPE_UNSUPPORTED_TEMPLATE = "Unsupported file type: {extension}"
 
FIELDS_UPDATE_MISSING = "No fields provided to update"
GEOMETRY_COMPUTE_UNAVAILABLE_TEMPLATE = "{operation} could not be computed"
VECTOR_UNION_REQUIRES_TWO = "At least two features are required for union"
VECTOR_BINARY_REQUIRES_TWO_TEMPLATE = "{label} requires exactly two features"
VECTOR_CONVEX_HULL_REQUIRES_TWO = "At least two features are required for convex hull"
VECTOR_COMPUTE_FAILURE_PREFIX = "Failed to compute "
VECTOR_UNION_FAILED = "Failed to compute union"
VECTOR_OPERATION_FAILED_TEMPLATE = "Failed to compute {operation}"
VECTOR_BUFFER_FAILED = "Failed to compute buffer"
VECTOR_CENTROID_FAILED = "Failed to compute centroid"
VECTOR_CONVEX_HULL_FAILED = "Failed to compute convex hull"
VECTOR_RESULT_SAVE_FAILED = "Failed to save vector operation result"
VECTOR_FEATURE_INVALID_GEOMETRY_TEMPLATE = "Selected feature {feature_name} has invalid geometry"
 
IMPLEMENTATION_MISSING = "Subclasses of BaseExtractor must override extract()"
CSV_PARSE_FAILED_TEMPLATE = "Failed to parse CSV: {reason}"
KML_PARSE_FAILED_TEMPLATE = "Failed to parse KML file: {reason}"
JSON_PARSE_FAILED_TEMPLATE = "Failed to parse JSON file: {reason}"
JSON_OBJECT_EXPECTED = "Unsupported JSON structure: expected a JSON object"
JSON_GEOJSON_EXPECTED = "Unsupported JSON structure: expected GeoJSON or a single_shape geometry"
GEOJSON_FEATURES_ARRAY_INVALID = "Invalid GeoJSON: features must be an array"
TIFF_READ_FAILED_TEMPLATE = "Failed to read TIFF file: {reason}"
WEBSOCKET_AUTH_REQUIRED = "Authentication required"
WEBSOCKET_POLICY_VIOLATION = 1008
GEOMETRY_VALIDITY_TEMPLATE = "{detail}: {reason}"
 
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
GEO_SEARCH_AREA_TOO_LARGE = " Search area is too large."
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
 
# ===================================================
# EMAIL DUMP INTEGRATION
# ===================================================
# GIS is a proxy for the external Email Dump Backend; it owns no email
# data of its own. Only the origin-IP endpoint is consumed, and its URL
# is always built from settings.EMAIL_DUMP_API_BASE_URL so the provider
# host is configurable and never hard-coded in service logic.
EMAIL_DUMP_ORIGIN_IPS_PATH = "/api/emails/single/origin-ips"
# Per-case dump listing. The case id is appended to this path, exactly as
# with the origin-IP endpoint; target_id is a query parameter.
EMAIL_DUMP_DUMPS_PATH = "/api/dumps/single"
# The provider exposes a per-case target list. It is not a nested path of
# the dumps endpoint: case_id is interpolated, so the prefix is a constant
# and only the leaf is appended.
EMAIL_DUMP_TARGETS_PREFIX_PATH = "/api/cases"

# One layer per upstream email_id, named deterministically so repeat
# imports reuse the same case-scoped layer instead of duplicating it.
EMAIL_DUMP_LAYER_TYPE = "email"
EMAIL_DUMP_LAYER_NAME_TEMPLATE = "Email {email_id}"
EMAIL_DUMP_FEATURE_NAME_TEMPLATE = "IP {ip}"

EMAIL_DUMP_NOT_CONFIGURED = (
    "Email Dump integration is not configured. Set EMAIL_DUMP_API_BASE_URL."
)

# ===================================================
# SATELLITE FEEDS
# ===================================================
# CelesTrak serves all GP data from a single query-string endpoint. The
# legacy static catalog file under /pub/TLE/ is no longer served, so the
# feed URL is configured as a base (settings.CELESTRAK_TLE_URL) and the
# requested group is always appended by the service rather than stored
# per group. This keeps the host configurable and the group list the
# single source of truth for both validation and URL construction.
#
# The Literal is the validation contract: FastAPI rejects an unknown
# group with 422 before the service is reached. SATELLITE_GROUPS is
# derived from it so the whitelist can never drift from the type.
SatelliteGroup = Literal[
    "active",
    "stations",
    "visual",
    "weather",
    "gps-ops",
    "starlink",
]

SATELLITE_GROUPS: frozenset[str] = frozenset(get_args(SatelliteGroup))

# Group used when the request omits the parameter, preserving the
# behaviour of the original full-catalog feed.
DEFAULT_SATELLITE_GROUP = "active"

# CelesTrak regenerates GP data on a coarse cadence and answers requests
# made inside that window with HTTP 403 and a plain-text body explaining
# that no newer data exists. This is a successful "nothing new" answer,
# not an outage: the service reuses the last good TLE set instead of
# surfacing a 503 to the client.
CELESTRAK_COOLDOWN_MARKER = "has not updated since your last successful"
CELESTRAK_COOLDOWN_STATUS = 403
EMAIL_DUMP_TIMEOUT = "Email Dump service timed out. Please try again."
EMAIL_DUMP_UNAVAILABLE = "Email Dump service is unavailable. Please try again."
EMAIL_DUMP_RATE_LIMITED = (
    "Email Dump service is rate limiting requests. Please try again later."
)
EMAIL_DUMP_UNAUTHORIZED = "Email Dump service rejected the provided credentials."
EMAIL_DUMP_NOT_FOUND = "No Email Dump origin-IP data was found for this case."
EMAIL_DUMP_INVALID_RESPONSE = "Email Dump service returned an invalid response."
EMAIL_DUMP_IMPORT_FAILED = "Failed to import Email Dump origin IPs"
EMAIL_DUMP_TARGET_NOT_FOUND = (
    "No Email Dump target was found for this case. Import the case's emails first."
)
EMAIL_DUMP_NO_DUMPS = "No Email Dump dumps were found for this target."
EMAIL_DUMP_INVALID_DUMPS_RESPONSE = (
    "Email Dump service returned an invalid response."
)
EMAIL_DUMP_DUMPS_FETCH_FAILED = (
    "Failed to fetch Email Dump dumps. Please try again."
)
EMAIL_DUMP_INVALID_TARGETS_RESPONSE = (
    "Email Dump service returned an invalid response."
)
EMAIL_DUMP_TARGETS_FETCH_FAILED = (
    "Failed to fetch Email Dump targets. Please try again."
)

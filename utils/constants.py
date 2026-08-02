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
AUTH_TOKEN_INVALID_OR_EXPIRED = "Invalid or expired token."
AUTH_TOKEN_PAYLOAD_INVALID = "Invalid token payload."
AUTH_ROLE_FORBIDDEN = "You do not have permission to perform this action."
AUTH_EMAIL_ALREADY_REGISTERED = "Email already registered"
AUTH_INVALID_EMAIL_OR_PASSWORD = "Invalid email or password"
AUTH_REGISTRATION_FAILED = "Failed to register user"
AUTH_LOGIN_FAILED = "Failed to process login"

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
LAYERS_FETCH_FAILED = "Failed to fetch layers"
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

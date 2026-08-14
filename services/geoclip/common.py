from utils.config import settings
from utils.constants import (
    DATABASE_SAVE_FAILED,
    GEOCLIP_NO_PREDICTIONS,
    GEOCLIP_PREDICTION_FAILED,
    GEOCLIP_TOP_K_RANGE_TEMPLATE,
    IMAGE_NOT_FOUND,
    IMAGE_READ_FAILED,
    LAYER_NOT_FOUND,
)
from utils.logger import logger
from utils.exceptions import (
    NotFoundError,
    BadRequestError,
    ServiceUnavailableError,
    UnprocessableEntityError,
)

# requesting e.g. top_k=100000 and hammering the model / DB.
MIN_TOP_K = 1
MAX_TOP_K = 20


def generate_layer_name(layer_id: int) -> str:
    return f"Untitled {layer_id}"


def _validate_top_k(top_k: int | None) -> int:
    if top_k is None:
        return settings.GEOCLIP_TOP_K

    if top_k < MIN_TOP_K or top_k > MAX_TOP_K:
        raise UnprocessableEntityError(
            GEOCLIP_TOP_K_RANGE_TEMPLATE.format(
                min_top_k=MIN_TOP_K,
                max_top_k=MAX_TOP_K,
                top_k=top_k,
            )
        )

    return top_k

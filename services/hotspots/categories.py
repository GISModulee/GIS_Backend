import json
from functools import lru_cache
from pathlib import Path

from utils.exceptions import BadRequestError, ServiceUnavailableError


CATEGORY_CONFIG_PATH = Path("config/hotspot_categories.json")


@lru_cache
def hotspot_categories() -> dict:
    try:
        with CATEGORY_CONFIG_PATH.open("r", encoding="utf-8") as handle:
            categories = json.load(handle)
    except OSError as exc:
        raise ServiceUnavailableError("Hotspot category configuration is unavailable") from exc

    if not isinstance(categories, dict) or not categories:
        raise ServiceUnavailableError("Hotspot category configuration is invalid")
    return categories


def selected_categories(groups: list[str]) -> dict:
    categories = hotspot_categories()
    selected = groups or list(categories)
    invalid = [group for group in selected if group not in categories]
    if invalid:
        raise BadRequestError(f"Invalid hotspot category group(s): {', '.join(invalid)}")
    return {group: categories[group] for group in selected}

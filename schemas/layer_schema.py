from pydantic import BaseModel, field_validator
from typing import Optional

from utils.constants import (
    ALLOWED_MODULE_SLUGS,
    MAX_MODULE_SLUG_LENGTH,
    MODULE_SLUG_EMPTY,
    MODULE_SLUG_INVALID,
    MODULE_SLUG_NOT_FOUND,
    MODULE_SLUG_REQUIRED,
    MODULE_SLUG_TOO_LONG,
)


class LayerCreate(BaseModel):
    case_id: Optional[int] = None
    name: str
    layer_type: str
    module_slug: str
    visible: bool = True

    @field_validator("module_slug", mode="before")
    @classmethod
    def _validate_module_slug(cls, value):
        if value is None:
            raise ValueError(MODULE_SLUG_REQUIRED)
        if not isinstance(value, str):
            raise ValueError(MODULE_SLUG_INVALID)
        slug = value.strip()
        if not slug:
            raise ValueError(MODULE_SLUG_EMPTY)
        if len(slug) > MAX_MODULE_SLUG_LENGTH:
            raise ValueError(MODULE_SLUG_TOO_LONG)
        if slug not in ALLOWED_MODULE_SLUGS:
            raise ValueError(MODULE_SLUG_NOT_FOUND)
        return slug


class LayerPatch(BaseModel):
    name: Optional[str] = None
    layer_type: Optional[str] = None
    visible: Optional[bool] = None


class LayerResponse(BaseModel):
    id: int
    case_id: Optional[int] = None
    name: str
    layer_type: str
    module_slug: str
    visible: bool


class LayerCreateResponse(BaseModel):
    success: bool
    layer_id: int
    message: str


class LayerActionResponse(BaseModel):
    success: bool
    message: str

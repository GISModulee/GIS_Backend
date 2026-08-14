from sqlalchemy import Integer, cast, func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from models.model import Layer, Case
from utils.constants import (
    CASE_NOT_FOUND,
    FIELDS_UPDATE_MISSING,
    LAYER_AUTO_CREATE_FAILED,
    LAYER_CREATE_CASE_NOT_FOUND_TEMPLATE,
    LAYER_CREATE_FAILED,
    LAYER_DELETE_FAILED,
    LAYER_DUPLICATE_IMPORT_CHECK_FAILED,
    LAYER_DUPLICATE_NAME_TEMPLATE,
    LAYER_DUPLICATE_SUFFIX_DEFAULT,
    LAYER_DUPLICATE_SUFFIX_IMPORT,
    LAYER_FETCH_FAILED,
    LAYER_NOT_FOUND,
    LAYER_UPDATE_FAILED,
)
from utils.logger import logger
from utils.exceptions import NotFoundError, BadRequestError, ConflictError, ServiceUnavailableError


# ===================================================
# NAME PREFIXES FOR SYSTEM-GENERATED LAYERS
# ===================================================
# Maps a layer_type to the naming prefix used for that type's
# auto-numbered layers, e.g. layer_type="auto" -> "Auto Layer 1",
# layer_type="vector" -> "Vector Layer 1". Add an entry here whenever
# a new kind of system-generated layer is introduced.

_AUTO_NAME_PREFIXES = {
    "auto": "Auto Layer",
    "vector": "Vector Layer",
}


async def _dict(layer):
    return {key: getattr(layer, key) for key in (
        "id", "case_id", "name", "layer_type", "visible", "created_at"
    )}


async def _duplicate(db, case_id, name, exclude_id=None):
    stmt = select(Layer.id).where(Layer.case_id == case_id, Layer.name == name)
    if exclude_id is not None:
        stmt = stmt.where(Layer.id != exclude_id)
    return db.scalar(stmt.limit(1))


async def _duplicate_error(name, import_layer=False):
    suffix = LAYER_DUPLICATE_SUFFIX_IMPORT if import_layer else LAYER_DUPLICATE_SUFFIX_DEFAULT
    return ConflictError(LAYER_DUPLICATE_NAME_TEMPLATE.format(name=name, suffix=suffix))


async def _integrity_error(error, case_id, name, import_layer=False):
    if getattr(getattr(error, "orig", None), "pgcode", None) == "23505":
        raise await _duplicate_error(name, import_layer) from error
    raise NotFoundError(LAYER_CREATE_CASE_NOT_FOUND_TEMPLATE.format(case_id=case_id)) from error


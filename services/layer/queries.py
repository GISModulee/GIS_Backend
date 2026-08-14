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
from services.layer.common import _dict

async def get_layers(db):
    try:
        return [await _dict(item) for item in db.scalars(select(Layer).order_by(Layer.id)).all()]
    except SQLAlchemyError as e:
        raise ServiceUnavailableError(LAYERS_FETCH_FAILED) from e


async def get_layer(layer_id: int, db):
    try:
        item = db.get(Layer, layer_id)
        return await _dict(item) if item else None
    except SQLAlchemyError as e:
        raise ServiceUnavailableError(LAYER_FETCH_FAILED) from e


async def get_case_layers(case_id: int, db):
    try:
        case_exists = db.scalar(select(Case.id).where(Case.id == case_id))
        if case_exists is None:
            logger.warning(f"Get case layers failed: case not found | case_id={case_id}")
            raise NotFoundError(CASE_NOT_FOUND)
        items = db.scalars(select(Layer).where(Layer.case_id == case_id).order_by(Layer.id)).all()
        return [await _dict(item) for item in items]
    except NotFoundError:
        raise
    except SQLAlchemyError as e:
        raise ServiceUnavailableError(LAYERS_FETCH_FAILED) from e

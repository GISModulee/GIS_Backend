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
from services.layer.common import _AUTO_NAME_PREFIXES, _duplicate, _duplicate_error, _integrity_error

async def update_layer(layer_id: int, layer: dict, db):
    try:
        item = db.get(Layer, layer_id)
        if item is None:
            raise NotFoundError(LAYER_NOT_FOUND)
        if await _duplicate(db, layer["case_id"], layer["name"], layer_id) is not None:
            raise await _duplicate_error(layer["name"])
        for key in ("case_id", "name", "layer_type", "visible"):
            setattr(item, key, layer[key])
        db.commit()
    except (NotFoundError, BadRequestError, ConflictError):
        raise
    except IntegrityError as e:
        db.rollback()
        await _integrity_error(e, layer.get("case_id"), layer.get("name"))
    except SQLAlchemyError as e:
        db.rollback()
        raise ServiceUnavailableError(LAYER_UPDATE_FAILED) from e
    return {"success": True, "message": "Layer updated successfully"}


async def delete_layer(layer_id, db):
    try:
        item = db.get(Layer, layer_id)
        if item is None:
            raise NotFoundError(LAYER_NOT_FOUND)
        case_id, name, layer_type = item.case_id, item.name, item.layer_type
        deleted_number = None
        prefix = _AUTO_NAME_PREFIXES.get(layer_type)
        if prefix is not None:
            try:
                deleted_number = int(name.replace(f"{prefix} ", ""))
            except (ValueError, AttributeError):
                pass
        db.delete(item)
        db.flush()
        if deleted_number is not None:
            remaining = db.scalars(select(Layer).where(
                Layer.case_id == case_id, Layer.layer_type == layer_type
            ).order_by(Layer.name)).all()
            for candidate in remaining:
                try:
                    number = int(candidate.name.replace(f"{prefix} ", ""))
                    if number > deleted_number:
                        candidate.name = f"{prefix} {number - 1}"
                except (ValueError, AttributeError):
                    continue
        db.commit()
    except NotFoundError:
        raise
    except SQLAlchemyError as e:
        db.rollback()
        raise ServiceUnavailableError(LAYER_DELETE_FAILED) from e
    return {"success": True, "message": "Layer deleted successfully"}

async def patch_layer(layer_id: int, layer: dict, db):
    updates = {key: value for key, value in layer.items() if key in {"name", "layer_type", "visible"} and value is not None}
    if not updates:
        raise BadRequestError(FIELDS_UPDATE_MISSING)
    try:
        item = db.get(Layer, layer_id)
        if item is None:
            raise NotFoundError(LAYER_NOT_FOUND)
        if "name" in updates and await _duplicate(db, item.case_id, updates["name"], layer_id) is not None:
            raise await _duplicate_error(updates["name"])
        for key, value in updates.items():
            setattr(item, key, value)
        db.commit()
    except (NotFoundError, BadRequestError, ConflictError):
        raise
    except IntegrityError as e:
        db.rollback()
        if getattr(getattr(e, "orig", None), "pgcode", None) == "23505":
            raise await _duplicate_error(updates.get("name")) from e
        raise ServiceUnavailableError(LAYER_UPDATE_FAILED) from e
    except SQLAlchemyError as e:
        db.rollback()
        raise ServiceUnavailableError(LAYER_UPDATE_FAILED) from e
    return {"success": True, "message": "Layer updated successfully"}

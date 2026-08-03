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
    LAYERS_FETCH_FAILED,
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


def _dict(layer):
    return {key: getattr(layer, key) for key in (
        "id", "case_id", "name", "layer_type", "visible", "created_at"
    )}


def _duplicate(db, case_id, name, exclude_id=None):
    stmt = select(Layer.id).where(Layer.case_id == case_id, Layer.name == name)
    if exclude_id is not None:
        stmt = stmt.where(Layer.id != exclude_id)
    return db.scalar(stmt.limit(1))


def _duplicate_error(name, import_layer=False):
    suffix = LAYER_DUPLICATE_SUFFIX_IMPORT if import_layer else LAYER_DUPLICATE_SUFFIX_DEFAULT
    return ConflictError(LAYER_DUPLICATE_NAME_TEMPLATE.format(name=name, suffix=suffix))


def _integrity_error(error, case_id, name, import_layer=False):
    if getattr(getattr(error, "orig", None), "pgcode", None) == "23505":
        raise _duplicate_error(name, import_layer) from error
    raise NotFoundError(LAYER_CREATE_CASE_NOT_FOUND_TEMPLATE.format(case_id=case_id)) from error


def create_layer(layer: dict, db):
    logger.info(f"Creating layer | case_id={layer.get('case_id')} | name={layer.get('name')}")
    try:
        existing_id = _duplicate(db, layer.get("case_id"), layer.get("name"))
        if existing_id is not None:
            if layer.get("layer_type") == "group":
                return {"success": True, "layer_id": existing_id, "message": "Reused existing layer"}
            raise _duplicate_error(layer.get("name"))
        record = Layer(**{key: layer[key] for key in ("case_id", "name", "layer_type", "visible")})
        db.add(record)
        db.commit()
        db.refresh(record)
        layer_id = record.id
    except (BadRequestError, ConflictError):
        raise
    except IntegrityError as e:
        db.rollback()
        _integrity_error(e, layer.get("case_id"), layer.get("name"))
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Failed to create layer | error={e}", exc_info=True)
        raise ServiceUnavailableError(LAYER_CREATE_FAILED) from e
    return {"success": True, "layer_id": layer_id, "message": "Layer created successfully"}


def get_import_layer_by_hash(case_id: int, file_hash: str, db):
    try:
        layer = db.scalar(select(Layer).where(
            Layer.case_id == case_id, Layer.file_hash == file_hash, Layer.layer_type == "import"
        ).limit(1))
        return _dict(layer) if layer else None
    except SQLAlchemyError as e:
        raise ServiceUnavailableError(LAYER_DUPLICATE_IMPORT_CHECK_FAILED) from e


def create_import_layer(case_id: int, name: str, file_hash: str, db):
    try:
        if _duplicate(db, case_id, name) is not None:
            raise _duplicate_error(name, True)
        record = Layer(case_id=case_id, name=name, layer_type="import", visible=True, file_hash=file_hash)
        db.add(record)
        db.commit()
        db.refresh(record)
        layer_id = record.id
    except (BadRequestError, ConflictError):
        raise
    except IntegrityError as e:
        db.rollback()
        _integrity_error(e, case_id, name, True)
    except SQLAlchemyError as e:
        db.rollback()
        raise ServiceUnavailableError(LAYER_CREATE_FAILED) from e
    return {"success": True, "layer_id": layer_id, "message": "Layer created successfully"}


def create_untitled_layer(case_id: int, db, layer_type: str = "auto"):
    """Create a system-numbered layer of the given layer_type.

    layer_type defaults to "auto" (regular feature creation without an
    explicit layer). Pass layer_type="vector" when auto-creating a
    layer to hold vector operation results (union/intersection/buffer/
    etc.), so it's visually and structurally distinct from ordinary
    auto layers in the case's layer list.
    """

    prefix = _AUTO_NAME_PREFIXES.get(layer_type)
    if prefix is None:
        raise BadRequestError(
            f"No auto-naming prefix configured for layer_type={layer_type!r}"
        )

    try:
        # Lock case to avoid duplicate auto layer numbers
        db.execute(
            select(func.pg_advisory_xact_lock(case_id))
        )

        max_number = db.scalar(
            select(
                func.coalesce(
                    func.max(
                        cast(
                            func.replace(
                                Layer.name,
                                f"{prefix} ",
                                ""
                            ),
                            Integer
                        ),
                    ),
                    0
                )
            )
            .where(
                Layer.case_id == case_id,
                Layer.layer_type == layer_type,
                Layer.name.like(f"{prefix} %")
            )
        )

        next_number = max_number + 1

        record = Layer(
            case_id=case_id,
            name=f"{prefix} {next_number}",
            layer_type=layer_type,
            visible=True
        )

        db.add(record)
        db.flush()

        return record.id


    except SQLAlchemyError as e:

        logger.error(
            f"Failed to auto-create layer | case_id={case_id} | layer_type={layer_type} | error={e}",
            exc_info=True
        )

        raise ServiceUnavailableError(
            LAYER_AUTO_CREATE_FAILED
        ) from e


def get_layers(db):
    try:
        return [_dict(item) for item in db.scalars(select(Layer).order_by(Layer.id)).all()]
    except SQLAlchemyError as e:
        raise ServiceUnavailableError(LAYERS_FETCH_FAILED) from e


def get_layer(layer_id: int, db):
    try:
        item = db.get(Layer, layer_id)
        return _dict(item) if item else None
    except SQLAlchemyError as e:
        raise ServiceUnavailableError(LAYER_FETCH_FAILED) from e


def update_layer(layer_id: int, layer: dict, db):
    try:
        item = db.get(Layer, layer_id)
        if item is None:
            raise NotFoundError(LAYER_NOT_FOUND)
        if _duplicate(db, layer["case_id"], layer["name"], layer_id) is not None:
            raise _duplicate_error(layer["name"])
        for key in ("case_id", "name", "layer_type", "visible"):
            setattr(item, key, layer[key])
        db.commit()
    except (NotFoundError, BadRequestError, ConflictError):
        raise
    except IntegrityError as e:
        db.rollback()
        _integrity_error(e, layer.get("case_id"), layer.get("name"))
    except SQLAlchemyError as e:
        db.rollback()
        raise ServiceUnavailableError(LAYER_UPDATE_FAILED) from e
    return {"success": True, "message": "Layer updated successfully"}


def delete_layer(layer_id, db):
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


def get_case_layers(case_id: int, db):
    try:
        case_exists = db.scalar(select(Case.id).where(Case.id == case_id))
        if case_exists is None:
            logger.warning(f"Get case layers failed: case not found | case_id={case_id}")
            raise NotFoundError(CASE_NOT_FOUND)
        items = db.scalars(select(Layer).where(Layer.case_id == case_id).order_by(Layer.id)).all()
        return [_dict(item) for item in items]
    except NotFoundError:
        raise
    except SQLAlchemyError as e:
        raise ServiceUnavailableError(LAYERS_FETCH_FAILED) from e


def patch_layer(layer_id: int, layer: dict, db):
    updates = {key: value for key, value in layer.items() if key in {"name", "layer_type", "visible"} and value is not None}
    if not updates:
        raise BadRequestError(FIELDS_UPDATE_MISSING)
    try:
        item = db.get(Layer, layer_id)
        if item is None:
            raise NotFoundError(LAYER_NOT_FOUND)
        if "name" in updates and _duplicate(db, item.case_id, updates["name"], layer_id) is not None:
            raise _duplicate_error(updates["name"])
        for key, value in updates.items():
            setattr(item, key, value)
        db.commit()
    except (NotFoundError, BadRequestError, ConflictError):
        raise
    except IntegrityError as e:
        db.rollback()
        if getattr(getattr(e, "orig", None), "pgcode", None) == "23505":
            raise _duplicate_error(updates.get("name")) from e
        raise ServiceUnavailableError(LAYER_UPDATE_FAILED) from e
    except SQLAlchemyError as e:
        db.rollback()
        raise ServiceUnavailableError(LAYER_UPDATE_FAILED) from e
    return {"success": True, "message": "Layer updated successfully"}
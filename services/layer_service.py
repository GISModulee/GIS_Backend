from sqlalchemy import Integer, cast, func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from database.database import SessionLocal
from models.model import Layer, Case
from utils.logger import logger
from utils.exceptions import NotFoundError, BadRequestError, ConflictError, ServiceUnavailableError


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
    suffix = "Pass a different 'layer_name' on the import request to disambiguate." if import_layer else "Choose a different name."
    return ConflictError(f"A layer named '{name}' already exists in this case. {suffix}")


def _integrity_error(error, case_id, name, import_layer=False):
    if getattr(getattr(error, "orig", None), "pgcode", None) == "23505":
        raise _duplicate_error(name, import_layer) from error
    raise NotFoundError(f"Cannot create layer: case_id {case_id} does not exist.") from error


def create_layer(layer: dict):
    logger.info(f"Creating layer | case_id={layer.get('case_id')} | name={layer.get('name')}")
    try:
        with SessionLocal.begin() as db:
            existing_id = _duplicate(db, layer.get("case_id"), layer.get("name"))
            if existing_id is not None:
                if layer.get("layer_type") == "group":
                    return {"success": True, "layer_id": existing_id, "message": "Reused existing layer"}
                raise _duplicate_error(layer.get("name"))
            record = Layer(**{key: layer[key] for key in ("case_id", "name", "layer_type", "visible")})
            db.add(record)
            db.flush()
            layer_id = record.id
    except (BadRequestError, ConflictError):
        raise
    except IntegrityError as e:
        _integrity_error(e, layer.get("case_id"), layer.get("name"))
    except SQLAlchemyError as e:
        logger.error(f"Failed to create layer | error={e}", exc_info=True)
        raise ServiceUnavailableError("Failed to create layer") from e
    return {"success": True, "layer_id": layer_id, "message": "Layer created successfully"}


def get_import_layer_by_hash(case_id: int, file_hash: str):
    try:
        with SessionLocal() as db:
            layer = db.scalar(select(Layer).where(
                Layer.case_id == case_id, Layer.file_hash == file_hash, Layer.layer_type == "import"
            ).limit(1))
            return _dict(layer) if layer else None
    except SQLAlchemyError as e:
        raise ServiceUnavailableError("Failed to check for duplicate import") from e


def create_import_layer(case_id: int, name: str, file_hash: str):
    try:
        with SessionLocal.begin() as db:
            if _duplicate(db, case_id, name) is not None:
                raise _duplicate_error(name, True)
            record = Layer(case_id=case_id, name=name, layer_type="import", visible=True, file_hash=file_hash)
            db.add(record)
            db.flush()
            layer_id = record.id
    except (BadRequestError, ConflictError):
        raise
    except IntegrityError as e:
        _integrity_error(e, case_id, name, True)
    except SQLAlchemyError as e:
        raise ServiceUnavailableError("Failed to create layer") from e
    return {"success": True, "layer_id": layer_id, "message": "Layer created successfully"}


def create_untitled_layer(case_id: int):
    try:
        with SessionLocal.begin() as db:
            db.execute(select(func.pg_advisory_xact_lock(case_id)))
            suffix = cast(func.replace(Layer.name, "Auto Layer ", ""), Integer)
            max_number = db.scalar(select(func.coalesce(func.max(suffix), 0)).where(
                Layer.case_id == case_id,
                Layer.layer_type == "auto",
                Layer.name.like("Auto Layer %"),
            ))
            for offset in range(1, 11):
                record = Layer(case_id=case_id, name=f"Auto Layer {max_number + offset}", layer_type="auto", visible=True)
                try:
                    with db.begin_nested():
                        db.add(record)
                        db.flush()
                    return record.id
                except IntegrityError as e:
                    if getattr(getattr(e, "orig", None), "pgcode", None) != "23505":
                        raise
            raise ServiceUnavailableError("Failed to auto-create layer: too many name collisions. Try again.")
    except ServiceUnavailableError:
        raise
    except SQLAlchemyError as e:
        raise ServiceUnavailableError("Failed to auto-create layer") from e


def get_layers():
    try:
        with SessionLocal() as db:
            return [_dict(item) for item in db.scalars(select(Layer).order_by(Layer.id)).all()]
    except SQLAlchemyError as e:
        raise ServiceUnavailableError("Failed to fetch layers") from e


def get_layer(layer_id: int):
    try:
        with SessionLocal() as db:
            item = db.get(Layer, layer_id)
            return _dict(item) if item else None
    except SQLAlchemyError as e:
        raise ServiceUnavailableError("Failed to fetch layer") from e


def update_layer(layer_id: int, layer: dict):
    try:
        with SessionLocal.begin() as db:
            item = db.get(Layer, layer_id)
            if item is None:
                raise NotFoundError("Layer not found")
            if _duplicate(db, layer["case_id"], layer["name"], layer_id) is not None:
                raise _duplicate_error(layer["name"])
            for key in ("case_id", "name", "layer_type", "visible"):
                setattr(item, key, layer[key])
    except (NotFoundError, BadRequestError, ConflictError):
        raise
    except IntegrityError as e:
        _integrity_error(e, layer.get("case_id"), layer.get("name"))
    except SQLAlchemyError as e:
        raise ServiceUnavailableError("Failed to update layer") from e
    return {"success": True, "message": "Layer updated successfully"}


def delete_layer(layer_id):
    try:
        with SessionLocal.begin() as db:
            item = db.get(Layer, layer_id)
            if item is None:
                raise NotFoundError("Layer not found")
            case_id, name, layer_type = item.case_id, item.name, item.layer_type
            deleted_number = None
            if layer_type == "auto":
                try:
                    deleted_number = int(name.replace("Auto Layer ", ""))
                except (ValueError, AttributeError):
                    pass
            db.delete(item)
            db.flush()
            if deleted_number is not None:
                remaining = db.scalars(select(Layer).where(
                    Layer.case_id == case_id, Layer.layer_type == "auto"
                ).order_by(Layer.name)).all()
                for candidate in remaining:
                    try:
                        number = int(candidate.name.replace("Auto Layer ", ""))
                        if number > deleted_number:
                            candidate.name = f"Auto Layer {number - 1}"
                    except (ValueError, AttributeError):
                        continue
    except NotFoundError:
        raise
    except SQLAlchemyError as e:
        raise ServiceUnavailableError("Failed to delete layer") from e
    return {"success": True, "message": "Layer deleted successfully"}


def get_case_layers(case_id: int):
    try:
        with SessionLocal() as db:
            case_exists = db.scalar(select(Case.id).where(Case.id == case_id))
            if case_exists is None:
                logger.warning(f"Get case layers failed: case not found | case_id={case_id}")
                raise NotFoundError("Case not found")
            items = db.scalars(select(Layer).where(Layer.case_id == case_id).order_by(Layer.id)).all()
            return [_dict(item) for item in items]
    except NotFoundError:
        raise
    except SQLAlchemyError as e:
        raise ServiceUnavailableError("Failed to fetch layers") from e


def patch_layer(layer_id: int, layer: dict):
    updates = {key: value for key, value in layer.items() if key in {"name", "layer_type", "visible"} and value is not None}
    if not updates:
        raise BadRequestError("No fields provided to update")
    try:
        with SessionLocal.begin() as db:
            item = db.get(Layer, layer_id)
            if item is None:
                raise NotFoundError("Layer not found")
            if "name" in updates and _duplicate(db, item.case_id, updates["name"], layer_id) is not None:
                raise _duplicate_error(updates["name"])
            for key, value in updates.items():
                setattr(item, key, value)
    except (NotFoundError, BadRequestError, ConflictError):
        raise
    except IntegrityError as e:
        if getattr(getattr(e, "orig", None), "pgcode", None) == "23505":
            raise _duplicate_error(updates.get("name")) from e
        raise ServiceUnavailableError("Failed to update layer") from e
    except SQLAlchemyError as e:
        raise ServiceUnavailableError("Failed to update layer") from e
    return {"success": True, "message": "Layer updated successfully"}
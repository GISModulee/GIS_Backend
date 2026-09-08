from sqlalchemy import Integer, cast, func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from models.model import Layer
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

async def create_layer(layer: dict, db):
    logger.info(f"Creating layer | case_id={layer.get('case_id')} | name={layer.get('name')}")
    try:
        existing_id = await _duplicate(db, layer.get("case_id"), layer.get("name"))
        if existing_id is not None:
            if layer.get("layer_type") == "group":
                return {"success": True, "layer_id": existing_id, "message": "Reused existing layer"}
            raise await _duplicate_error(layer.get("name"))
        record = Layer(**{key: layer[key] for key in ("case_id", "name", "layer_type", "visible")})
        db.add(record)
        db.commit()
        db.refresh(record)
        layer_id = record.id
    except (BadRequestError, ConflictError):
        raise
    except IntegrityError as e:
        db.rollback()
        await _integrity_error(e, layer.get("case_id"), layer.get("name"))
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Failed to create layer | error={e}", exc_info=True)
        raise ServiceUnavailableError(LAYER_CREATE_FAILED) from e
    return {"success": True, "layer_id": layer_id, "message": "Layer created successfully"}


async def get_import_layer_by_hash(case_id: int, file_hash: str, db):
    try:
        layer = db.scalar(select(Layer).where(
            Layer.case_id == case_id, Layer.file_hash == file_hash, Layer.layer_type == "import"
        ).limit(1))
        return await _dict(layer) if layer else None
    except SQLAlchemyError as e:
        raise ServiceUnavailableError(LAYER_DUPLICATE_IMPORT_CHECK_FAILED) from e


async def create_import_layer(case_id: int, name: str, file_hash: str, db):
    try:
        if await _duplicate(db, case_id, name) is not None:
            raise await _duplicate_error(name, True)
        record = Layer(case_id=case_id, name=name, layer_type="import", visible=True, file_hash=file_hash)
        db.add(record)
        db.commit()
        db.refresh(record)
        layer_id = record.id
    except (BadRequestError, ConflictError):
        raise
    except IntegrityError as e:
        db.rollback()
        await _integrity_error(e, case_id, name, True)
    except SQLAlchemyError as e:
        db.rollback()
        raise ServiceUnavailableError(LAYER_CREATE_FAILED) from e
    return {"success": True, "layer_id": layer_id, "message": "Layer created successfully"}


async def create_untitled_layer(case_id: int, db, layer_type: str = "auto"):
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


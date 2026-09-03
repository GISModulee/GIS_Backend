import os

import anyio
from fastapi import UploadFile
from starlette.concurrency import run_in_threadpool

from services.upload_data.registry import EXTRACTOR_REGISTRY
from services.upload_data.storage import UPLOAD_FOLDER, _sanitize_filename
from services.feature.feature_websocket_manager import feature_connection_manager
from utils.constants import UPLOAD_TYPE_UNSUPPORTED_TEMPLATE
from utils.exceptions import UnsupportedMediaTypeError
from utils.logger import logger

CHUNK_SIZE = 2000


async def _broadcast_batch_created(
    case_id: int,
    layer_id: int,
    features: list[dict],
    chunk_index: int,
) -> None:
    """
    Broadcasts one committed import batch. The caller is responsible
    for keeping each batch bounded to CHUNK_SIZE.
    """
    if not features:
        return

    await feature_connection_manager.broadcast(
        case_id,
        {
            "event": "feature.batch_created",
            "case_id": case_id,
            "layer_id": layer_id,
            "chunk_index": chunk_index,
            "total_chunks": None,
            "count": len(features),
            "features": features,
        },
    )


async def _broadcast_import_completed(
    case_id: int,
    layer_id: int,
    imported_features: int,
    total_chunks: int,
) -> None:
    await feature_connection_manager.broadcast(
        case_id,
        {
            "event": "feature.batch_import_completed",
            "case_id": case_id,
            "layer_id": layer_id,
            "imported_features": imported_features,
            "total_chunks": total_chunks,
        },
    )


async def process_upload(
    case_id: int,
    file: UploadFile,
    db,
    layer_name: str | None = None,
    created_by: int | None = None,
):

    extension = os.path.splitext(file.filename or "")[1].lstrip(".").lower()
    extractor = EXTRACTOR_REGISTRY.get(extension)
    if extractor is None:
        raise UnsupportedMediaTypeError(UPLOAD_TYPE_UNSUPPORTED_TEMPLATE.format(extension=extension))

    safe_name = _sanitize_filename(file.filename)
    file_path = os.path.join(UPLOAD_FOLDER, safe_name)

    with open(file_path, "wb") as f:
        f.write(await file.read())

    batch_state = {"chunk_index": 0}

    def broadcast_created_batch(layer_id: int, created_features: list[dict]) -> None:
        chunk_index = batch_state["chunk_index"]
        batch_state["chunk_index"] += 1
        try:
            anyio.from_thread.run(
                _broadcast_batch_created,
                case_id,
                layer_id,
                created_features,
                chunk_index,
            )
        except Exception as broadcast_error:
            logger.exception(
                "Feature batch WebSocket broadcast failed after batch commit | "
                "case_id=%s | layer_id=%s | chunk_index=%s | error=%s",
                case_id,
                layer_id,
                chunk_index,
                broadcast_error,
            )

    try:
        data = await run_in_threadpool(
            extractor.extract,
            file_path=file_path,
            filename=file.filename,
            case_id=case_id,
            layer_name=layer_name,
            created_by=created_by,
            db=db,
            batch_size=CHUNK_SIZE,
            on_batch_created=broadcast_created_batch,
        )
    except Exception:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except OSError as cleanup_error:
            logger.warning(
                "Failed to clean up upload file after extraction error | path=%s | error=%s",
                file_path,
                cleanup_error,
            )
        raise

    if data.get("status") == "imported" and data.get("layer_id") is not None:
        try:
            await _broadcast_import_completed(
                case_id,
                data["layer_id"],
                data.get("imported_features", 0),
                batch_state["chunk_index"],
            )
        except Exception as completion_error:
            logger.exception(
                "Feature batch import completion broadcast failed | "
                "case_id=%s | layer_id=%s | error=%s",
                case_id,
                data["layer_id"],
                completion_error,
            )

    return {
        "success": True,
        "case_id": case_id,
        "filename": file.filename,
        "file_type": extension,
        "data": data
    }

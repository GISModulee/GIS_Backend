import os

from fastapi import UploadFile
from starlette.concurrency import run_in_threadpool

from services.upload_data.registry import EXTRACTOR_REGISTRY
from services.upload_data.storage import UPLOAD_FOLDER, _sanitize_filename
from services.feature.feature_websocket_manager import feature_connection_manager
from utils.constants import UPLOAD_TYPE_UNSUPPORTED_TEMPLATE
from utils.exceptions import UnsupportedMediaTypeError

CHUNK_SIZE = 2000


async def _broadcast_batch_created(case_id: int, layer_id: int, features: list[dict]) -> None:
    """
    Broadcasts newly-imported features in chunks of CHUNK_SIZE so no
    single WebSocket frame carries an unbounded number of features.
    Each chunk is a complete, independently-processable
    feature.batch_created event, safe for the frontend to consume
    one at a time as they arrive.
    """
    if not features:
        return

    total = len(features)
    chunks = [features[i:i + CHUNK_SIZE] for i in range(0, total, CHUNK_SIZE)]

    for idx, chunk in enumerate(chunks):
        await feature_connection_manager.broadcast(
            case_id,
            {
                "event": "feature.batch_created",
                "case_id": case_id,
                "layer_id": layer_id,
                "chunk_index": idx,
                "total_chunks": len(chunks),
                "count": len(chunk),
                "features": chunk,
            },
        )


async def process_upload(
    case_id: int,
    file: UploadFile,
    db,
    layer_name: str | None = None,
    created_by: int | None = None,
):

    safe_name = _sanitize_filename(file.filename)
    file_path = os.path.join(UPLOAD_FOLDER, safe_name)

    with open(file_path, "wb") as f:
        f.write(await file.read())

    extension = file.filename.split(".")[-1].lower()

    extractor = EXTRACTOR_REGISTRY.get(extension)
    if extractor is None:
        raise UnsupportedMediaTypeError(UPLOAD_TYPE_UNSUPPORTED_TEMPLATE.format(extension=extension))

    data = await run_in_threadpool(
        extractor.extract,
        file_path=file_path,
        filename=file.filename,
        case_id=case_id,
        layer_name=layer_name,
        created_by=created_by,
        db=db,
    )

    if data.get("status") == "imported" and data.get("created_features"):
        await _broadcast_batch_created(case_id, data["layer_id"], data["created_features"])

    return {
        "success": True,
        "case_id": case_id,
        "filename": file.filename,
        "file_type": extension,
        "data": data
    }

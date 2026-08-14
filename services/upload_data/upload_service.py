import os

from fastapi import UploadFile
from starlette.concurrency import run_in_threadpool

from services.upload_data.registry import EXTRACTOR_REGISTRY
from services.upload_data.storage import UPLOAD_FOLDER, _sanitize_filename
from utils.constants import UPLOAD_TYPE_UNSUPPORTED_TEMPLATE
from utils.exceptions import UnsupportedMediaTypeError


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

    return {
        "success": True,
        "case_id": case_id,
        "filename": file.filename,
        "file_type": extension,
        "data": data
    }

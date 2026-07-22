from fastapi import APIRouter, Depends, UploadFile, File, Form

from services.upload_service import process_upload
from utils.dependencies import require_roles
from utils.roles import CAN_UPLOAD
from utils.logger import logger

router = APIRouter(
    tags=["Uploads"]
)


# ===================================================
# GENERIC FILE IMPORT (CSV/KML/TIFF) — Admin, Officer, Analyst
# ===================================================
@router.post("/import")
async def upload_file(
    case_id: int = Form(...),
    file: UploadFile = File(...),
    layer_name: str | None = Form(
        None,
        description="Optional name for the layer created from this import (KML only). "
                    "Defaults to the uploaded file's name if omitted."
    ),
    current_user=Depends(require_roles(CAN_UPLOAD))
):
    logger.info(
        f"POST /import | user_id={current_user['user_id']} | role={current_user['role']} | "
        f"case_id={case_id} | filename={file.filename} | layer_name={layer_name}"
    )
    return await process_upload(
        case_id,
        file,
        layer_name=layer_name,
        created_by=current_user["user_id"],
    )

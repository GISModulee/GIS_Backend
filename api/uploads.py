from fastapi import APIRouter, Depends, UploadFile, File, Form

from services.upload_service import process_upload
from utils.dependencies import require_roles
from utils.roles import CAN_UPLOAD
from utils.logger import logger

router = APIRouter(
    tags=["Uploads"]
)


# ===================================================
# GENERIC FILE UPLOAD (CSV/KML/TIFF) — Admin, Officer, Analyst
# ===================================================
@router.post("/upload")
async def upload_file(
    case_id: int = Form(...),
    file: UploadFile = File(...),
    current_user=Depends(require_roles(CAN_UPLOAD))
):
    logger.info(f"POST /upload | user_id={current_user['user_id']} | role={current_user['role']} | case_id={case_id} | filename={file.filename}")
    return await process_upload(case_id, file)
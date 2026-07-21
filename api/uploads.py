<<<<<<< Updated upstream
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
# NOTE: renamed from "/upload" to "/import" — GeoCLIP's image-upload
# router now lives at "/upload" (previously "/api/v1/upload"), and two
# routers can't both claim the same path+method. "/import" also better
# describes what this route actually does (importing case data files),
# as distinct from uploading an image for geolocation.
@router.post("/import")
async def upload_file(
    case_id: int = Form(...),
    file: UploadFile = File(...),
    current_user=Depends(require_roles(CAN_UPLOAD))
):
    logger.info(f"POST /import | user_id={current_user['user_id']} | role={current_user['role']} | case_id={case_id} | filename={file.filename}")
=======
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
>>>>>>> Stashed changes
    return await process_upload(case_id, file)
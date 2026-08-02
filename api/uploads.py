from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.orm import Session

from database.database import get_db
from services.upload_service import process_upload
from schemas.upload_schema import UploadResponse
from utils.dependencies import require_roles
from utils.roles import CAN_UPLOAD
from utils.logger import logger
from typing import Annotated

router = APIRouter(
    tags=["Uploads"]
)


@router.post("/import", response_model=UploadResponse)
async def upload_file(
    case_id: Annotated[int, Form(...)],
    file: Annotated[UploadFile, File()],
    current_user: Annotated[
        dict,
        Depends(require_roles(CAN_UPLOAD)),
    ],
    db: Annotated[Session, Depends(get_db)],
    layer_name: Annotated[
        str | None,
        Form(
            description=(
                "Optional name for the layer created from this import. "
                "Defaults to the uploaded filename if omitted."
            ),
        ),
    ] = None,
):
    logger.info(
        f"POST /import | "
        f"user_id={current_user['user_id']} | "
        f"role={current_user['role']} | "
        f"case_id={case_id} | "
        f"filename={file.filename} | "
        f"layer_name={layer_name}"
    )

    return await process_upload(
        case_id=case_id,
        file=file,
        db=db,
        layer_name=layer_name,
        created_by=current_user["user_id"],
    )
 

from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.orm import Session

from database.database import get_db
from services.upload_data.upload_service import process_upload
from services.feature.feature_service import get_feature
from services.layer.layer_service import get_layer
from services.layer.layer_websocket_manager import layer_connection_manager
from services.feature.feature_websocket_manager import feature_connection_manager
from schemas.upload_schema import UploadResponse
from utils.dependencies import authorize_case, enforce_role, get_access_token
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
    access_token: Annotated[str, Depends(get_access_token)],
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
    current_user = enforce_role(await authorize_case(access_token, case_id), CAN_UPLOAD)
    logger.info(
        f"POST /import | "
        f"user_id={current_user['user_id']} | "
        f"role={current_user['role']} | "
        f"case_id={case_id} | "
        f"filename={file.filename} | "
        f"layer_name={layer_name}"
    )

    result = await process_upload(
        case_id=case_id,
        file=file,
        db=db,
        layer_name=layer_name,
        created_by=current_user["user_id"],
    )

    data = result.get("data") or {}
    if data.get("status") == "imported" and data.get("layer_id") is not None:
        created_layer = await get_layer(data["layer_id"], db)
        message = {
            "event": "layer.created",
            "case_id": case_id,
            "layer": created_layer,
        }
        await layer_connection_manager.broadcast(
            case_id,
            message,
        )
        await feature_connection_manager.broadcast(
            case_id,
            message,
        )
        for feature_id in data.get("feature_ids") or []:
            created_feature = await get_feature(feature_id, db)
            if created_feature is None:
                continue
            await feature_connection_manager.broadcast(
                case_id,
                {
                    "event": "feature.created",
                    "case_id": case_id,
                    "layer_id": data["layer_id"],
                    "feature": created_feature,
                },
            )

    return result
 

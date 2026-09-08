from typing import Annotated, List

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.orm import Session

from database.database import get_db
from models.model import ImageRecord
from schemas.geoclip_schema import (
    FeatureCollectionResponse,
    ImageResponse,
    ImageUploadResponse,
    LayerActionResponse,
)
from services.geoclip.service import (
    delete_layer as delete_layer_service,
    get_features_by_layer as get_features_by_layer_service,
    get_image as get_image_service,
    get_images_by_layer as get_images_by_layer_service,
    upload_image as upload_image_service,
)
from services.feature.feature_service import get_feature
from services.layer.layer_service import get_layer
from services.layer.layer_websocket_manager import layer_connection_manager
from services.feature.feature_websocket_manager import feature_connection_manager
from utils.dependencies import authorize_case, enforce_role, get_access_token
from utils.exceptions import NotFoundError
from utils.constants import IMAGE_NOT_FOUND, LAYER_NOT_FOUND
from utils.roles import CAN_UPLOAD, CAN_DELETE_OPERATIONAL
from utils.logger import logger

router = APIRouter()

@router.post(
    "/upload",
    response_model=ImageUploadResponse,
    summary="Upload image and create GeoCLIP layer",
)
async def upload_image(
    file: Annotated[UploadFile, File(...)],
    db: Annotated[Session, Depends(get_db)],
    case_id: Annotated[int, Form(...)],
    access_token: str = Depends(get_access_token),
    top_k: Annotated[
        int | None,
        Form(description="Number of location predictions to generate (1-20). Defaults to server setting if omitted.")
    ] = None,
    layer_name: Annotated[
        str | None,
        Form(description="Optional name for the layer created from this upload. Defaults to 'Untitled {layer_id}' if omitted.")
    ] = None,
):
    current_user = enforce_role(await authorize_case(access_token, case_id), CAN_UPLOAD)
    logger.info(
        f"POST /upload | user_id={current_user['user_id']} | role={current_user['role']} | "
        f"case_id={case_id} | filename={file.filename} | top_k={top_k} | layer_name={layer_name}"
    )
    result = await upload_image_service(
        file,
        db,
        case_id=case_id,
        top_k=top_k,
        layer_name=layer_name,
        created_by=current_user["user_id"],
    )
    if result.get("status") == "success" and result.get("layer_id") is not None:
        created_layer = await get_layer(result["layer_id"], db)
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
        for feature_id in result.get("feature_ids") or []:
            created_feature = await get_feature(feature_id, db)
            if created_feature is None:
                continue
            await feature_connection_manager.broadcast(
                case_id,
                {
                    "event": "feature.created",
                    "case_id": case_id,
                    "layer_id": result["layer_id"],
                    "feature": created_feature,
                },
            )
    return result


@router.get(
    "/layers/{layer_id}/images",
    response_model=List[ImageResponse],
)
async def get_images_by_layer(
    layer_id: int,
    db: Annotated[Session, Depends(get_db)],
    access_token: str = Depends(get_access_token),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    layer = await get_layer(layer_id, db)
    if layer is None:
        raise NotFoundError(LAYER_NOT_FOUND)
    current_user = await authorize_case(access_token, layer["case_id"])
    """Paginated: defaults to 100 rows per page, use ?limit=&offset= to page."""
    logger.info(
        f"GET /layers/{layer_id}/images | user_id={current_user['user_id']} | "
        f"limit={limit} | offset={offset}"
    )
    return await get_images_by_layer_service(layer_id, limit, offset, db)


@router.get(
    "/geoclip/layers/{layer_id}/features",
    response_model=FeatureCollectionResponse,
)
async def get_features_by_layer(
    layer_id: int,
    db: Annotated[Session, Depends(get_db)],
    access_token: str = Depends(get_access_token),
    limit: int = Query(500, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    layer = await get_layer(layer_id, db)
    if layer is None:
        raise NotFoundError(LAYER_NOT_FOUND)
    current_user = await authorize_case(access_token, layer["case_id"])
    logger.info(
        f"GET /layers/{layer_id}/features | user_id={current_user['user_id']} | "
        f"limit={limit} | offset={offset}"
    )
    return await get_features_by_layer_service(layer_id, limit, offset, db)


@router.get("/image/{image_id}")
async def get_image(
    image_id: str,
    db: Annotated[Session, Depends(get_db)],
    access_token: str = Depends(get_access_token),
):
    image = db.get(ImageRecord, image_id)
    if image is None:
        raise NotFoundError(IMAGE_NOT_FOUND)
    layer = await get_layer(image.layer_id, db)
    if layer is None:
        raise NotFoundError(LAYER_NOT_FOUND)
    current_user = await authorize_case(access_token, layer["case_id"])
    logger.info(f"GET /image/{image_id} | user_id={current_user['user_id']}")
    return await get_image_service(image_id, db)


@router.delete(
    "/geoclip/layers/{layer_id}",
    response_model=LayerActionResponse,
)
async def delete_layer(
    layer_id: int,
    db: Annotated[Session, Depends(get_db)],
    access_token: str = Depends(get_access_token),
):
    layer = await get_layer(layer_id, db)
    if layer is None:
        raise NotFoundError(LAYER_NOT_FOUND)
    current_user = enforce_role(await authorize_case(access_token, layer["case_id"]), CAN_DELETE_OPERATIONAL)
    logger.warning(f"DELETE /layers/{layer_id} | user_id={current_user['user_id']} | role={current_user['role']}")
    existing_layer = layer
    result = await delete_layer_service(layer_id, db)

    if existing_layer:
        message = {
            "event": "layer.deleted",
            "case_id": existing_layer["case_id"],
            "layer_id": layer_id,
        }
        await layer_connection_manager.broadcast(
            existing_layer["case_id"],
            message,
        )
        await feature_connection_manager.broadcast(
            existing_layer["case_id"],
            message,
        )

    return result

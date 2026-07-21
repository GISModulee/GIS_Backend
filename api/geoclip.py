from typing import Annotated, List

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from database.database import get_db
from schemas.geoclip_schema import (
    FeatureCollectionResponse,
    ImageResponse,
    ImageUploadResponse,
    LayerActionResponse,
    LayerRenameRequest,
)
from services.geoclip_service import (
    delete_layer as delete_layer_service,
    get_features_by_layer as get_features_by_layer_service,
    get_image as get_image_service,
    get_images_by_layer as get_images_by_layer_service,
    rename_layer as rename_layer_service,
    upload_image as upload_image_service,
)
from utils.dependencies import get_current_user, require_roles
from utils.roles import CAN_UPLOAD, CAN_WRITE, CAN_DELETE_OPERATIONAL
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
    current_user=Depends(require_roles(CAN_UPLOAD)),
    top_k: Annotated[
        int | None,
        Form(description="Number of location predictions to generate (1-20). Defaults to server setting if omitted.")
    ] = None,
):
    logger.info(
        f"POST /upload | user_id={current_user['user_id']} | role={current_user['role']} | "
        f"filename={file.filename} | top_k={top_k}"
    )
    return await upload_image_service(file, db, top_k=top_k)


@router.get(
    "/layers/{layer_id}/images",
    response_model=List[ImageResponse],
)
def get_images_by_layer(
    layer_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user=Depends(get_current_user),
    limit: int = 100,
    offset: int = 0,
):
    """Paginated: defaults to 100 rows per page, use ?limit=&offset= to page."""
    logger.info(
        f"GET /layers/{layer_id}/images | user_id={current_user['user_id']} | "
        f"limit={limit} | offset={offset}"
    )
    return get_images_by_layer_service(layer_id, limit, offset, db)


@router.get(
    "/layers/{layer_id}/features",
    response_model=FeatureCollectionResponse,
)
def get_features_by_layer(
    layer_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user=Depends(get_current_user),
    limit: int = 500,
    offset: int = 0,
):
    logger.info(
        f"GET /layers/{layer_id}/features | user_id={current_user['user_id']} | "
        f"limit={limit} | offset={offset}"
    )
    return get_features_by_layer_service(layer_id, limit, offset, db)


@router.get("/image/{image_id}")
def get_image(
    image_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user=Depends(get_current_user),
):
    logger.info(f"GET /image/{image_id} | user_id={current_user['user_id']}")
    return get_image_service(image_id, db)


@router.delete(
    "/layers/{layer_id}",
    response_model=LayerActionResponse,
)
def delete_layer(
    layer_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user=Depends(require_roles(CAN_DELETE_OPERATIONAL)),
):
    logger.warning(f"DELETE /layers/{layer_id} | user_id={current_user['user_id']} | role={current_user['role']}")
    return delete_layer_service(layer_id, db)


@router.patch(
    "/layers/{layer_id}",
    response_model=LayerActionResponse,
)
def rename_layer(
    layer_id: int,
    body: LayerRenameRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user=Depends(require_roles(CAN_WRITE)),
):
    logger.info(f"PATCH /layers/{layer_id} | user_id={current_user['user_id']} | role={current_user['role']} | new_name={body.name}")
    return rename_layer_service(layer_id, body.name, db)



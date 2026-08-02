import json
import time
import uuid
from typing import List

from fastapi import UploadFile
from fastapi.responses import Response
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from utils.config import settings
from utils.logger import logger
from utils.exceptions import (
    NotFoundError,
    BadRequestError,
    ConflictError,
    ServiceUnavailableError,
    UnprocessableEntityError,
)
from models.model import Feature, ImageRecord, Layer
from schemas.feature_schema import FeatureCreate
from services.geoclip_processor import FileUtils, ImageProcessor
from services.geoclip_validator import FileValidator
from services.layer_service import create_layer, patch_layer
from services.feature_service import create_feature

# Sane bounds for a user-supplied top_k — prevents someone from
# requesting e.g. top_k=100000 and hammering the model / DB.
MIN_TOP_K = 1
MAX_TOP_K = 20


def generate_layer_name(layer_id: int) -> str:
    return f"Untitled {layer_id}"


def _validate_top_k(top_k: int | None) -> int:
    if top_k is None:
        return settings.GEOCLIP_TOP_K

    if top_k < MIN_TOP_K or top_k > MAX_TOP_K:
        raise UnprocessableEntityError(
            f"top_k must be between {MIN_TOP_K} and {MAX_TOP_K} (got {top_k})."
        )

    return top_k

def upload_image(
    file: UploadFile,
    db: Session,
    case_id: int,
    top_k: int | None = None,
    layer_name: str | None = None,
    created_by: int | None = None,
):

    start_time = time.monotonic()

    effective_top_k = _validate_top_k(top_k)

    logger.info(
        f"Processing GeoCLIP upload | case_id={case_id} | filename={file.filename} | "
        f"top_k={effective_top_k} | layer_name={layer_name} | created_by={created_by}"
    )

    FileValidator.validate_extension(file.filename)

   
    try:
        content = file.file.read()
    except Exception as e:
        logger.error(f"Failed to read uploaded file | filename={file.filename} | error={e}", exc_info=True)
        raise BadRequestError("Unable to read uploaded file") from e

    # --- 3. Size validation ---
    FileValidator.validate_size(content, settings.MAX_FILE_SIZE_BYTES)

    # --- 4. Content-type (magic byte) validation ---
    real_extension, detected_mime = FileValidator.validate_magic_bytes(content, file.filename)

    # --- 5. Duplicate check ---
    file_hash = FileUtils.get_file_hash(content)
    existing = db.query(ImageRecord).filter(ImageRecord.file_hash == file_hash).first()

    if existing:
        logger.info(f"Duplicate upload detected | file_hash={file_hash} | existing_id={existing.id}")
        return {
            "id": existing.id,
            "layer_id": existing.layer_id,
            "layer_name": existing.layer.name,
            "filename": existing.filename,
            "predictions_created": 0,
            "data": existing.raw_metadata,
            "status": "already_processed",
        }

    try:
        result = ImageProcessor.process_and_predict(content, real_extension, effective_top_k)
    except Exception as e:
        logger.error(f"Prediction failed | filename={file.filename} | error={e}", exc_info=True)
        raise ServiceUnavailableError("GeoCLIP prediction failed") from e

    if not result.get("predictions"):
        logger.error(f"No predictions returned | filename={file.filename}")
        raise UnprocessableEntityError("No location predictions could be generated for this image.")

    predictions = result["predictions"]
    top_prediction = predictions[0]

    # --- 8. Create the layer via the shared layer_service ---
    layer_result = create_layer({
        "case_id": case_id,
        "name": layer_name if layer_name else "__pending__",
        "layer_type": "geoclip_prediction",
        "visible": True,
    }, db)
    layer_id = layer_result["layer_id"]

    if layer_name:
        resolved_layer_name = layer_name
    else:
        resolved_layer_name = generate_layer_name(layer_id)
        patch_layer(layer_id, {"name": resolved_layer_name}, db)

    # --- 9. Create one Feature per prediction via the shared feature_service ---
    file_id = str(uuid.uuid4())
    created_feature_ids = []

    for rank, pred in enumerate(predictions, start=1):

        feature_name = (
            file.filename if len(predictions) == 1
            else f"{file.filename} (prediction {rank})"
        )

        feature_in = FeatureCreate(
            case_id=case_id,
            layer_id=layer_id,
            name=feature_name,
            geometry={
                "type": "Point",
                "coordinates": [pred["lon"], pred["lat"]],
            },
            geometry_type="Point",
            properties={
                "type": "point",
                "layerType": "point",
                "layer_type": "point",
                "category": "GeoCLIP Prediction",
                "color": "#dc2626",
                "image_id": file_id,
                "filename": file.filename,
                "source": result.get("source"),
                "rank": rank,
                "lat": pred["lat"],
                "lon": pred["lon"],
                "score": pred["score"],
            },
        )

        feature_result = create_feature(feature_in, db, created_by)
        created_feature_ids.append(feature_result["feature_id"])

    
    try:
        image = ImageRecord(
            id=file_id,
            file_hash=file_hash,
            layer_id=layer_id,
            image_data=content,
            filename=file.filename,
            content_type=detected_mime,
            raw_metadata=result,
            location=f"SRID=4326;POINT({top_prediction['lon']} {top_prediction['lat']})",
        )
        db.add(image)
        db.commit()

    except IntegrityError as e:
        db.rollback()
        logger.warning(f"Duplicate upload race detected | file_hash={file_hash} | error={e}")

        existing = db.query(ImageRecord).filter(ImageRecord.file_hash == file_hash).first()

        if existing:
            return {
                "id": existing.id,
                "layer_id": existing.layer_id,
                "layer_name": existing.layer.name,
                "filename": existing.filename,
                "predictions_created": 0,
                "data": existing.raw_metadata,
                "status": "already_processed",
            }

        raise ServiceUnavailableError("Database save failed") from e

    elapsed = time.monotonic() - start_time
    logger.info(
        f"Upload complete | layer={layer_id} | features_created={len(created_feature_ids)} | time={elapsed:.2f}s"
    )

    return {
        "id": file_id,
        "layer_id": layer_id,
        "layer_name": resolved_layer_name,
        "filename": file.filename,
        "predictions_created": len(predictions),
        "data": result,
        "status": "success",
    }


# ===================================================
# GET IMAGES OF A LAYER (PAGINATED)
# ===================================================
# FIX: previously ran the query with no check that layer_id exists.
# A nonexistent layer_id returned an empty list `[]` — indistinguishable
# from a real layer with zero images. Now verifies the layer exists
# first and raises NotFoundError (404) if not.
def get_images_by_layer(layer_id: int, limit: int, offset: int, db: Session) -> List[ImageRecord]:

    logger.info(f"Fetching images for layer | layer_id={layer_id} | limit={limit} | offset={offset}")

    layer_exists = db.query(Layer.id).filter(Layer.id == layer_id).first()
    if layer_exists is None:
        logger.warning(f"Get images by layer failed: layer not found | layer_id={layer_id}")
        raise NotFoundError("Layer not found")

    limit = max(1, min(limit, 500))
    offset = max(0, offset)

    return (
        db.query(ImageRecord)
        .filter(ImageRecord.layer_id == layer_id)
        .order_by(ImageRecord.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


# ===================================================
# GET FEATURES OF A LAYER (GEOJSON)
# ===================================================
# FIX: previously ran the query with no check that layer_id exists.
# A nonexistent layer_id returned an empty FeatureCollection —
# indistinguishable from a real layer with zero features. Now verifies
# the layer exists first and raises NotFoundError (404) if not.
def get_features_by_layer(layer_id: int, limit: int, offset: int, db: Session) -> dict:

    logger.info(f"Fetching features for layer | layer_id={layer_id} | limit={limit} | offset={offset}")

    layer_exists = db.query(Layer.id).filter(Layer.id == layer_id).first()
    if layer_exists is None:
        logger.warning(f"Get features by layer failed: layer not found | layer_id={layer_id}")
        raise NotFoundError("Layer not found")

    limit = max(1, min(limit, 2000))
    offset = max(0, offset)

    rows = (
        db.query(
            Feature.id,
            Feature.layer_id,
            Feature.name,
            Feature.properties,
            func.ST_AsGeoJSON(Feature.geom).label("geometry_json"),
        )
        .filter(Feature.layer_id == layer_id)
        .order_by(Feature.id)
        .offset(offset)
        .limit(limit)
        .all()
    )

    features = []
    for row in rows:
        try:
            geometry = json.loads(row.geometry_json) if row.geometry_json else None
        except (TypeError, ValueError) as e:
            logger.error(f"Malformed geometry JSON for feature_id={row.id}: {e}")
            geometry = None

        features.append({
            "type": "Feature",
            "id": row.id,
            "layer_id": row.layer_id,
            "name": row.name,
            "geometry": geometry,
            "properties": row.properties or {},
        })

    return {"type": "FeatureCollection", "features": features}


# ===================================================
# GET SINGLE IMAGE (RAW BYTES)
# ===================================================
def get_image(image_id: str, db: Session) -> Response:

    logger.info(f"Fetching image | image_id={image_id}")

    record = db.query(ImageRecord).filter(ImageRecord.id == image_id).first()

    if not record:
        logger.warning(f"Image not found | image_id={image_id}")
        raise NotFoundError("Image not found")

    return Response(content=record.image_data, media_type=record.content_type or "image/jpeg")


# ===================================================
# DELETE LAYER (+ CHILDREN)
# ===================================================
def delete_layer(layer_id: int, db: Session) -> dict:

    logger.warning(f"Deleting GeoCLIP layer | layer_id={layer_id}")

    layer = db.query(Layer).filter(Layer.id == layer_id).first()

    if not layer:
        logger.warning(f"Layer not found | layer_id={layer_id}")
        raise NotFoundError("Layer not found")

    layer_name = layer.name

    db.query(Feature).filter(Feature.layer_id == layer_id).delete(synchronize_session=False)
    db.query(ImageRecord).filter(ImageRecord.layer_id == layer_id).delete(synchronize_session=False)
    db.delete(layer)
    db.commit()

    logger.info(f"Layer deleted | id={layer_id} | name={layer_name} ")
    return {"id": layer_id, "name": layer_name, "status": "deleted"}


# ===================================================
# RENAME LAYER
# ===================================================
def rename_layer(layer_id: int, new_name: str, db: Session) -> dict:

    logger.info(f"Renaming GeoCLIP layer | layer_id={layer_id} | new_name={new_name}")

    new_name = new_name.strip()
    if not new_name:
        raise BadRequestError("Layer name cannot be empty")

    layer = db.query(Layer).filter(Layer.id == layer_id).first()

    if not layer:
        logger.warning(f"Layer not found | layer_id={layer_id}")
        raise NotFoundError("Layer not found")

    duplicate = (
        db.query(Layer.id)
        .filter(
            Layer.case_id == layer.case_id,
            Layer.name == new_name,
            Layer.id != layer_id,
        )
        .first()
    )
    if duplicate is not None:
        logger.warning(
            f"Layer rename rejected: duplicate name in case | "
            f"layer_id={layer_id} | case_id={layer.case_id} | name={new_name}"
        )
        raise ConflictError(
            f"A layer named '{new_name}' already exists in this case. "
            "Choose a different name."
        )

    layer.name = new_name
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        if getattr(getattr(e, "orig", None), "pgcode", None) == "23505":
            raise ConflictError(
                f"A layer named '{new_name}' already exists in this case. "
                "Choose a different name."
            ) from e
        raise

    logger.info(f"Layer renamed | id={layer_id} | new_name={new_name}")
    return {"id": layer_id, "name": new_name, "status": "renamed"}

import json
import time
import uuid
from typing import List

from fastapi import UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from utils.config import settings
from utils.logger import logger
from utils.exception_handler import (
    NotFoundError,
    BadRequestError,
    ServiceUnavailableError,
    UnprocessableEntityError,
)
from models.model import Feature, ImageRecord, Layer
from services.geoclip_processor import FileUtils, ImageProcessor
from services.geoclip_validator import FileValidator


def generate_layer_name(layer_id: int) -> str:
    return f"Untitled {layer_id}"


# ===================================================
# UPLOAD IMAGE
# ===================================================
async def upload_image(file: UploadFile, db: Session):

    start_time = time.monotonic()
    logger.info(f"Processing GeoCLIP upload | filename={file.filename}")

    # --- 1. Extension validation ---
    FileValidator.validate_extension(file.filename)

    # --- 2. Read file bytes ---
    try:
        content = await file.read()
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

    # --- 6. Run prediction ---
    try:
        result = await run_in_threadpool(ImageProcessor.process_and_predict, content, real_extension)
    except Exception as e:
        logger.error(f"Prediction failed | filename={file.filename} | error={e}", exc_info=True)
        raise ServiceUnavailableError("GeoCLIP prediction failed") from e

    if not result.get("predictions"):
        logger.error(f"No predictions returned | filename={file.filename}")
        raise UnprocessableEntityError("No location predictions could be generated for this image.")

    # --- 7. Persist layer + image + feature ---
    try:
        file_id = str(uuid.uuid4())
        layer = Layer(
            name="__pending__",
            layer_type="geoclip_prediction",
            visible=True,
        )
        db.add(layer)
        db.flush()  # get layer.id without committing
        layer.name = generate_layer_name(layer.id)

        top_prediction = result["predictions"][0]

        image = ImageRecord(
            id=file_id,
            file_hash=file_hash,
            layer_id=layer.id,
            image_data=content,
            filename=file.filename,
            content_type=detected_mime,
            raw_metadata=result,
            location=f"SRID=4326;POINT({top_prediction['lon']} {top_prediction['lat']})",
        )
        db.add(image)
        multipoint_wkt = "MULTIPOINT(" + ", ".join(
            f"{pred['lon']} {pred['lat']}" for pred in result["predictions"]
        ) + ")"

        feature = Feature(
            layer_id=layer.id,
            name=file.filename,
            geom=f"SRID=4326;{multipoint_wkt}",
            geometry_type="MultiPoint",
            properties={
                "type": "multipoint",
                "layerType": "multipoint",
                "layer_type": "multipoint",
                "category": "GeoCLIP Prediction",
                "color": "#dc2626",
                "image_id": file_id,
                "filename": file.filename,
                "source": result.get("source"),
                "points": [
                    {
                        "rank": index + 1,
                        "lat": pred["lat"],
                        "lon": pred["lon"],
                        "score": pred["score"],
                    }
                    for index, pred in enumerate(result["predictions"])
                ],
            },
        )
        db.add(feature)
        db.commit()

    except IntegrityError as e:
        # Two concurrent uploads of the same file raced past the
        # duplicate check above — recover by returning the row that won.
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
    logger.info(f"Upload complete | layer={layer.id} | time={elapsed:.2f}s")

    return {
        "id": file_id,
        "layer_id": layer.id,
        "layer_name": layer.name,
        "filename": file.filename,
        "predictions_created": len(result["predictions"]),
        "data": result,
        "status": "success",
    }


# ===================================================
# GET IMAGES OF A LAYER (PAGINATED)
# ===================================================
def get_images_by_layer(layer_id: int, limit: int, offset: int, db: Session) -> List[ImageRecord]:

    logger.info(f"Fetching images for layer | layer_id={layer_id} | limit={limit} | offset={offset}")

    limit = max(1, min(limit, 500))  # hard ceiling to prevent abuse
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
def get_features_by_layer(layer_id: int, limit: int, offset: int, db: Session) -> dict:

    logger.info(f"Fetching features for layer | layer_id={layer_id} | limit={limit} | offset={offset}")

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

    # Uses the real MIME type detected and stored at upload time,
    # falling back to jpeg only for legacy rows saved before this
    # column existed.
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

    # Delete children first — no ON DELETE CASCADE assumed on the FKs.
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

    layer.name = new_name
    db.commit()

    logger.info(f"Layer renamed | id={layer_id} | new_name={new_name}")
    return {"id": layer_id, "name": new_name, "status": "renamed"}

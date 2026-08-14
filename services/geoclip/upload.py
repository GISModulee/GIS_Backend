import time
import uuid

from fastapi import UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.model import ImageRecord
from schemas.feature_schema import FeatureCreate
from services.feature.feature_service import create_feature
from services.geoclip.common import generate_layer_name, _validate_top_k
from services.geoclip.processor import FileUtils, ImageProcessor
from services.geoclip.validator import FileValidator
from services.layer.layer_service import create_layer, patch_layer
from utils.config import settings
from utils.constants import DATABASE_SAVE_FAILED, GEOCLIP_NO_PREDICTIONS, GEOCLIP_PREDICTION_FAILED, IMAGE_READ_FAILED
from utils.exceptions import BadRequestError, ServiceUnavailableError, UnprocessableEntityError
from utils.logger import logger

async def upload_image(
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
        raise BadRequestError(IMAGE_READ_FAILED) from e

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
        raise ServiceUnavailableError(GEOCLIP_PREDICTION_FAILED) from e

    if not result.get("predictions"):
        logger.error(f"No predictions returned | filename={file.filename}")
        raise UnprocessableEntityError(GEOCLIP_NO_PREDICTIONS)

    predictions = result["predictions"]
    top_prediction = predictions[0]

    # --- 8. Create the layer via the shared layer_service ---
    layer_result = await create_layer({
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
    created_feature_numbers = []

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

        feature_result = await create_feature(feature_in, db, created_by)
        created_feature_ids.append(feature_result["feature_id"])
        created_feature_numbers.append(feature_result["feature_number"])

    
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

        raise ServiceUnavailableError(DATABASE_SAVE_FAILED) from e

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
        "feature_ids": created_feature_ids,
        "feature_numbers": created_feature_numbers,
        "data": result,
        "status": "success",
    }

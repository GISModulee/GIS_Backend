import json
from typing import List

from fastapi.responses import Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from models.model import Feature, ImageRecord, Layer
from utils.constants import IMAGE_NOT_FOUND, LAYER_NOT_FOUND
from utils.exceptions import NotFoundError
from utils.logger import logger

def get_images_by_layer(layer_id: int, limit: int, offset: int, db: Session) -> List[ImageRecord]:

    logger.info(f"Fetching images for layer | layer_id={layer_id} | limit={limit} | offset={offset}")

    layer_exists = db.query(Layer.id).filter(Layer.id == layer_id).first()
    if layer_exists is None:
        logger.warning(f"Get images by layer failed: layer not found | layer_id={layer_id}")
        raise NotFoundError(LAYER_NOT_FOUND)

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
async def get_features_by_layer(layer_id: int, limit: int, offset: int, db: Session) -> dict:

    logger.info(f"Fetching features for layer | layer_id={layer_id} | limit={limit} | offset={offset}")

    layer_exists = db.query(Layer.id).filter(Layer.id == layer_id).first()
    if layer_exists is None:
        logger.warning(f"Get features by layer failed: layer not found | layer_id={layer_id}")
        raise NotFoundError(LAYER_NOT_FOUND)

    limit = max(1, min(limit, 2000))
    offset = max(0, offset)

    rows = (
        db.query(
            Feature.id,
            Feature.layer_id,
            Feature.feature_number,
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
            "feature_number": row.feature_number,
            "name": row.name,
            "geometry": geometry,
            "properties": row.properties or {},
        })

    return {"type": "FeatureCollection", "features": features}


# ===================================================
# GET SINGLE IMAGE (RAW BYTES)
# ===================================================
async def get_image(image_id: str, db: Session) -> Response:

    logger.info(f"Fetching image | image_id={image_id}")

    record = db.query(ImageRecord).filter(ImageRecord.id == image_id).first()

    if not record:
        logger.warning(f"Image not found | image_id={image_id}")
        raise NotFoundError(IMAGE_NOT_FOUND)

    return Response(content=record.image_data, media_type=record.content_type or "image/jpeg")


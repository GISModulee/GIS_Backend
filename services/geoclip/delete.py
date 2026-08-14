from sqlalchemy.orm import Session

from models.model import Feature, ImageRecord, Layer
from utils.constants import LAYER_NOT_FOUND
from utils.exceptions import NotFoundError
from utils.logger import logger

async def delete_layer(layer_id: int, db: Session) -> dict:

    logger.warning(f"Deleting GeoCLIP layer | layer_id={layer_id}")

    layer = db.query(Layer).filter(Layer.id == layer_id).first()

    if not layer:
        logger.warning(f"Layer not found | layer_id={layer_id}")
        raise NotFoundError(LAYER_NOT_FOUND)

    layer_name = layer.name

    db.query(Feature).filter(Feature.layer_id == layer_id).delete(synchronize_session=False)
    db.query(ImageRecord).filter(ImageRecord.layer_id == layer_id).delete(synchronize_session=False)
    db.delete(layer)
    db.commit()

    logger.info(f"Layer deleted | id={layer_id} | name={layer_name} ")
    return {"id": layer_id, "name": layer_name, "status": "deleted"}

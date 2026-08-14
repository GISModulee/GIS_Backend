from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from models.reference_layer import ReferenceLayer


def _get_reference_layers(db: Session):
    return (
        db.query(ReferenceLayer)
        .order_by(ReferenceLayer.id)
        .all()
    )


async def get_reference_layers(db: Session):
    return await run_in_threadpool(
        _get_reference_layers,
        db,
    )

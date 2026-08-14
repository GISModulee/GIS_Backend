from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database.database import get_db
from services.reference.reference_layer_service import get_reference_layers

router = APIRouter(
    prefix="/reference",
    tags=["Reference Layers"],
)


@router.get("/layers")
async def list_reference_layers(
    db: Session = Depends(get_db),
):
    return await get_reference_layers(db)
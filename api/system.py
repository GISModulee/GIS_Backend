from fastapi import APIRouter

from schemas.system_schema import HealthResponse, HomeResponse
from utils.logger import logger


router = APIRouter()


@router.get("/health", tags=["System"], response_model=HealthResponse)
async def health_check():

    logger.info("Health check accessed")

    return {
        "status": "online",
        "message": "GeoIntelligence API is running.",
    }


@router.get("/", response_model=HomeResponse)
async def home():

    logger.info("Home endpoint accessed")

    return {
        "message": "API Running"
    }

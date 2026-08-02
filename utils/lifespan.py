from contextlib import asynccontextmanager

from fastapi import FastAPI

from services.geoclip.model import geo_model
from utils.config import settings
from utils.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):

    logger.info("Starting up GeoIntelligence API")

    logger.info(
        f"Config | MAX_FILE_MB={settings.MAX_FILE_SIZE_MB} | "
        f"TOP_K={settings.GEOCLIP_TOP_K}"
    )

    geo_model.load_model()

    logger.info("GIS Backend started successfully")

    yield

    logger.info("Shutting down GeoIntelligence API.")

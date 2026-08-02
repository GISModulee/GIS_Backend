from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from services.geoclip_model import geo_model

from utils.logger import logger
from utils.config import settings
from utils.request_context import (
    new_request_id,
    set_request_id,
)
from utils.exception_handler import register_exception_handlers
from schemas.system_schema import HealthResponse, HomeResponse

from middleware.logging_middleware import LoggingMiddleware

from api.features import router as feature_router
from api.layers import router as layer_router
from api.comments import router as comment_router
from api.cases import router as case_router
from api.uploads import router as upload_router

from api.geoclip import router as geoclip_router

from api.auth import router as auth_router
from api.vector import router as vector_router
from api.geo_search import router as geo_search_router


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


app = FastAPI(
    title="GeoIntelligence API",
    description="Pipeline for Geographic Information System.",
    version="2.1.0",
    lifespan=lifespan,
)

register_exception_handlers(app)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):

    incoming_id = request.headers.get("X-Request-ID")

    request_id = incoming_id or new_request_id()

    set_request_id(request_id)

    response = await call_next(request)

    response.headers["X-Request-ID"] = request_id
    
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=[
        "GET",
        "POST",
        "PUT",
        "PATCH",
        "DELETE"
    ],
    allow_headers=["*"],
)


app.add_middleware(LoggingMiddleware)


# Routers

app.include_router(auth_router)

app.include_router(geoclip_router, tags=["Images"])

app.include_router(feature_router)
app.include_router(layer_router)
app.include_router(comment_router)
app.include_router(case_router)
app.include_router(upload_router)
app.include_router(vector_router)
app.include_router(geo_search_router)


@app.get("/health", tags=["System"], response_model=HealthResponse)
def health_check():

    logger.info("Health check accessed")

    return {
        "status": "online",
        "message": "GeoIntelligence API is running.",
    }


@app.get("/", response_model=HomeResponse)
def home():

    logger.info("Home endpoint accessed")

    return {
        "message": "API Running"
    }

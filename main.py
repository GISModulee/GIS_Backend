from fastapi import FastAPI

from api.router import register_routers
from middleware.setup import register_middlewares
from utils.exception_handler import register_exception_handlers
from utils.lifespan import lifespan


app = FastAPI(
    title="GeoIntelligence API",
    description="Pipeline for Geographic Information System.",
    version="2.1.0",
    lifespan=lifespan,
)

register_exception_handlers(app)
register_middlewares(app)
register_routers(app)

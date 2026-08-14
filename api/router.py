from fastapi import FastAPI

from api.auth import router as auth_router
from api.cases import router as case_router
from api.collaboration import router as collaboration_router
from api.comments import router as comment_router
from api.comments_read import router as comment_read_router
from api.comments_ws import router as comment_ws_router
from api.features import router as feature_router
from api.features_read import router as feature_read_router
from api.features_ws import router as feature_ws_router
from api.geo_search import router as geo_search_router
from api.geoclip import router as geoclip_router
from api.layers import router as layer_router
from api.system import router as system_router
from api.uploads import router as upload_router
from api.vector import router as vector_router
from api.reference_layer import router as reference_layer_router


def register_routers(app: FastAPI) -> None:
    app.include_router(auth_router)

    app.include_router(geoclip_router, tags=["Images"])

    app.include_router(feature_router)
    app.include_router(feature_read_router)
    app.include_router(feature_ws_router)
    app.include_router(layer_router)
    app.include_router(comment_router)
    app.include_router(comment_read_router)
    app.include_router(comment_ws_router)
    app.include_router(collaboration_router)
    app.include_router(case_router)
    app.include_router(upload_router)
    app.include_router(vector_router)
    app.include_router(geo_search_router)
    app.include_router(system_router)
    app.include_router(reference_layer_router)

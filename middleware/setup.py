from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from middleware.logging_middleware import LoggingMiddleware
from middleware.request_id import request_id_middleware


def register_middlewares(app: FastAPI) -> None:
    app.middleware("http")(request_id_middleware)

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

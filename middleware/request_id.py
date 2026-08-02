from fastapi import Request

from utils.request_context import (
    new_request_id,
    set_request_id,
)


async def request_id_middleware(request: Request, call_next):

    incoming_id = request.headers.get("X-Request-ID")

    request_id = incoming_id or new_request_id()

    set_request_id(request_id)

    response = await call_next(request)

    response.headers["X-Request-ID"] = request_id

    return response

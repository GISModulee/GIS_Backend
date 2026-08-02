from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    message: str


class HomeResponse(BaseModel):
    message: str

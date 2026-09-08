from pydantic import (
    BaseModel,
    EmailStr,
)


class CurrentUserResponse(BaseModel):
    """The currently authenticated user, as validated by Central
    Intelligence. GIS does not own a local User source of truth."""

    user_id: int
    email: EmailStr
    role: str
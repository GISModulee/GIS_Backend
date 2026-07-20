from datetime import datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
)


class UserRole(str, Enum):
    ADMIN = "Admin"
    OFFICER = "Officer"
    ANALYST = "Analyst"
    VIEWER = "Viewer"


class RegisterUser(BaseModel):
    full_name: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="User full name"
    )

    email: EmailStr

    password: str = Field(
        ...,
        min_length=8,
        max_length=128
    )

    role: UserRole

    @field_validator("full_name")
    @classmethod
    def validate_name(cls, value: str):
        value = value.strip()
        if len(value.split()) < 2:
            raise ValueError("Please enter first name and last name.")
        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str):
        if not any(c.isupper() for c in value):
            raise ValueError("Password must contain an uppercase letter.")
        if not any(c.islower() for c in value):
            raise ValueError("Password must contain a lowercase letter.")
        if not any(c.isdigit() for c in value):
            raise ValueError("Password must contain a number.")
        special = "!@#$%^&*()-_=+[]{}|;:',.<>?/"
        if not any(c in special for c in value):
            raise ValueError("Password must contain a special character.")
        return value


class LoginUser(BaseModel):
    """
    No `role` field here on purpose. The role is looked up from the
    database after the password is verified — the client never needs
    to (and shouldn't) tell the server what role a user has. Sending
    it as input would mean trusting the client's claim about its own
    permissions, which isn't something to verify against, it's
    something to look up.
    """

    email: EmailStr

    password: str = Field(
        ...,
        min_length=8,
        max_length=128
    )


class UserResponse(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    full_name: str
    role: UserRole
    created_at: datetime
    last_login: Optional[datetime] = None


class RegisterResponse(BaseModel):

    success: bool
    message: str
    user: UserResponse


class TokenResponse(BaseModel):

    success: bool = True
    message: str = "Login successful"
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: UserResponse


class CurrentUserResponse(BaseModel):

    user_id: int
    email: EmailStr
    role: UserRole
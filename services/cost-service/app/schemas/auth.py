"""
CloudPulse AI - Cost Service
Pydantic schemas for authentication and user management.
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _looks_like_email(value: str) -> str:
    normalized = value.strip()
    if "@" not in normalized:
        raise ValueError("Email must contain @")

    local_part, domain = normalized.rsplit("@", maxsplit=1)
    if not local_part or not domain or "." not in domain:
        raise ValueError("Email must include a local part and domain")

    return normalized


class Token(BaseModel):
    """Token response schema."""
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    csrf_token: str | None = None


class TokenPayload(BaseModel):
    """Token payload schema."""
    sub: str | None = None
    type: str | None = None
    csrf: str | None = None
    jti: str | None = None
    exp: int | None = None


class UserBase(BaseModel):
    """Base user schema."""
    email: str
    full_name: str | None = None
    is_active: bool = True

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return _looks_like_email(value)


class UserCreate(UserBase):
    """User creation schema."""
    password: str = Field(..., min_length=8)
    organization_name: str = Field(..., min_length=2)


class UserUpdate(BaseModel):
    """User update schema."""
    email: str | None = None
    password: str | None = Field(None, min_length=8)
    full_name: str | None = None
    is_active: bool | None = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _looks_like_email(value)


class UserResponse(UserBase):
    """User response schema."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    role: str
    created_at: datetime


class LoginRequest(BaseModel):
    """Login request schema."""
    username: str  # We use email as username
    password: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        return _looks_like_email(value)


class RefreshTokenRequest(BaseModel):
    """Refresh token request schema."""
    refresh_token: str | None = None


class LogoutRequest(BaseModel):
    """Logout request schema."""
    access_token: str | None = None
    refresh_token: str | None = None

"""
CloudPulse AI - Cost Service
Pydantic schemas for authentication and user management.
"""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class Token(BaseModel):
    """Token response schema."""
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """Token payload schema."""
    sub: str | None = None


class UserBase(BaseModel):
    """Base user schema."""
    email: EmailStr
    full_name: str | None = None
    is_active: bool = True


class UserCreate(UserBase):
    """User creation schema."""
    password: str = Field(..., min_length=8)
    organization_name: str = Field(..., min_length=2)


class UserUpdate(BaseModel):
    """User update schema."""
    email: EmailStr | None = None
    password: str | None = Field(None, min_length=8)
    full_name: str | None = None
    is_active: bool | None = None


class UserResponse(UserBase):
    """User response schema."""
    id: str
    organization_id: str
    role: str
    created_at: datetime

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    """Login request schema."""
    username: EmailStr  # We use email as username
    password: str

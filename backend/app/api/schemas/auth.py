"""Auth-related API schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.models import Role


class RegisterRequest(BaseModel):
    tenant_name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9-]+$")
    owner_email: str = Field(min_length=3, max_length=200)
    owner_password: str = Field(min_length=8, max_length=200)


class RegisterResponse(BaseModel):
    tenant_id: str
    owner_id: str


class LoginRequest(BaseModel):
    tenant_id: str
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CreateUserRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)
    role: Role


class CreateAPIKeyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    role: Role


class APIKeyResponse(BaseModel):
    id: str
    name: str
    prefix: str
    role: Role
    api_key: str  # full key, shown once

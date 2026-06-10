"""Identity & tenancy tables: tenants, users, API keys."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel

from app.db.models._base import Role, utcnow, uuid_str


class Tenant(SQLModel, table=True):
    __tablename__ = "tenants"

    id: str = Field(default_factory=uuid_str, primary_key=True)
    name: str = Field(index=True)
    slug: str = Field(sa_column_kwargs={"unique": True})
    created_at: datetime = Field(default_factory=utcnow)
    is_active: bool = Field(default=True)


class User(SQLModel, table=True):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("tenant_id", "email", name="uq_user_email"),)

    id: str = Field(default_factory=uuid_str, primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    email: str = Field(index=True)
    hashed_password: str
    role: Role = Field(sa_column=Column(SAEnum(Role)))
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=utcnow)


class APIKey(SQLModel, table=True):
    __tablename__ = "api_keys"

    id: str = Field(default_factory=uuid_str, primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    name: str
    prefix: str = Field(index=True)
    hashed_secret: str
    role: Role = Field(sa_column=Column(SAEnum(Role)))
    created_at: datetime = Field(default_factory=utcnow)
    last_used_at: datetime | None = Field(default=None)
    revoked: bool = Field(default=False)

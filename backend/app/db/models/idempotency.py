"""Idempotency key table â€” dedupes replayed mutating requests."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.db.models._base import AwareDateTime, JSONType, utcnow


class IdempotencyKeyRow(SQLModel, table=True):
    __tablename__ = "idempotency_keys"
    __table_args__ = (
        UniqueConstraint("tenant_id", "key", name="uq_idempotency_key"),
    )

    id: str = Field(default=None, primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    key: str = Field(index=True)
    method: str
    path: str
    response_code: int
    response_body: dict = Field(default_factory=dict, sa_column=Column(JSONType))
    created_at: datetime = Field(default_factory=utcnow, sa_type=AwareDateTime)

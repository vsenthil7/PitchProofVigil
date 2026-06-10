"""Audit log table — immutable record of significant domain events."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, Index
from sqlmodel import Field, SQLModel

from app.db.models._base import JSONType, utcnow, uuid_str


class AuditLogRow(SQLModel, table=True):
    __tablename__ = "audit_log"
    __table_args__ = (Index("ix_audit_tenant_created", "tenant_id", "created_at"),)

    id: str = Field(default_factory=uuid_str, primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    actor: str = Field(default="system", index=True)
    action: str = Field(index=True)
    target: str = Field(default="")
    detail: dict = Field(default_factory=dict, sa_column=Column(JSONType))
    created_at: datetime = Field(default_factory=utcnow, index=True)

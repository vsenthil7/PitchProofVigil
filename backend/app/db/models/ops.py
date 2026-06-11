"""Operational tables: alerts (audit, webhooks added in later sprints)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, Index
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel

from app.db.models._base import AwareDateTime, AlertChannel, JSONType, utcnow, uuid_str


class AlertRow(SQLModel, table=True):
    __tablename__ = "alerts"
    __table_args__ = (Index("ix_alert_tenant_created", "tenant_id", "created_at"),)

    id: str = Field(default_factory=uuid_str, primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    severity: str = Field(index=True)
    title: str
    body: str
    channel: AlertChannel = Field(sa_column=Column(SAEnum(AlertChannel)))
    context: dict = Field(default_factory=dict, sa_column=Column(JSONType))
    delivered: bool = Field(default=False)
    created_at: datetime = Field(default_factory=utcnow, index=True, sa_type=AwareDateTime)

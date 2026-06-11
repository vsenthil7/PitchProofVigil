"""Webhook subscription table â€” per-tenant, per-event-type delivery targets."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Index, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.db.models._base import AwareDateTime, utcnow, uuid_str


class WebhookSubscriptionRow(SQLModel, table=True):
    __tablename__ = "webhook_subscriptions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "url", "event_type", name="uq_webhook"),
        Index("ix_webhook_tenant_event", "tenant_id", "event_type"),
    )

    id: str = Field(default_factory=uuid_str, primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    url: str
    event_type: str = Field(index=True)
    secret: str = Field(default="")
    active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=utcnow, sa_type=AwareDateTime)
    last_delivery_at: datetime | None = Field(default=None, sa_type=AwareDateTime)
    last_status: int | None = Field(default=None)

"""Trace & span tables."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, Index
from sqlmodel import Field, SQLModel

from app.db.models._base import JSONType, utcnow, uuid_str


class TraceRow(SQLModel, table=True):
    __tablename__ = "traces"
    __table_args__ = (Index("ix_traces_tenant_created", "tenant_id", "created_at"),)

    id: str = Field(primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    request_text: str
    language: str
    intent: str | None = Field(default=None, index=True)
    response_text: str | None = Field(default=None)
    model: str | None = Field(default=None)
    latency_ms: float = Field(default=0.0)
    grounded_facts: dict = Field(default_factory=dict, sa_column=Column(JSONType))
    created_at: datetime = Field(default_factory=utcnow, index=True)


class SpanRow(SQLModel, table=True):
    __tablename__ = "spans"

    id: str = Field(default_factory=uuid_str, primary_key=True)
    trace_id: str = Field(foreign_key="traces.id", index=True)
    tenant_id: str = Field(index=True)
    parent_id: str | None = Field(default=None)
    name: str
    kind: str
    status: str = Field(default="OK")
    duration_ms: float = Field(default=0.0)
    attributes: dict = Field(default_factory=dict, sa_column=Column(JSONType))
    start_time: datetime = Field(default_factory=utcnow)

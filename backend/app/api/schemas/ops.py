"""Operational API schemas: audit log and webhook subscriptions."""
from __future__ import annotations

from pydantic import BaseModel, Field


class AuditEntryOut(BaseModel):
    id: str
    actor: str
    action: str
    target: str
    detail: dict
    created_at: str


class CreateWebhookRequest(BaseModel):
    url: str = Field(min_length=1, max_length=500)
    event_type: str = Field(min_length=1, max_length=64)
    secret: str = Field(default="", max_length=200)


class WebhookOut(BaseModel):
    id: str
    url: str
    event_type: str
    active: bool
    last_status: int | None


class TrendPointOut(BaseModel):
    bucket: str
    value: float
    count: int


class AnalyticsSummaryOut(BaseModel):
    window_hours: int
    evaluations: int
    pass_rate: float


class DriftPointOut(BaseModel):
    bucket: str
    mean_score: float
    p10: float
    p90: float
    pass_rate: float
    count: int

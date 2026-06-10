"""API request/response schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.core.models import (
    DriftPoint,
    EvalResult,
    GateDecision,
    IntentType,
    Language,
    Trace,
)


class AskRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    language: Language = Language.EN


class AskResponse(BaseModel):
    trace: Trace
    eval_results: list[EvalResult]
    aggregate_score: float


class GateRequest(BaseModel):
    candidate: str = Field(min_length=1, max_length=200)
    queries: list[str] = Field(min_length=1, max_length=100)
    language: Language = Language.EN


class HealthResponse(BaseModel):
    status: str
    modes: dict[str, str]
    trace_count: int


class DriftResponse(BaseModel):
    point: DriftPoint
    alerting: bool


__all__ = [
    "AskRequest",
    "AskResponse",
    "GateRequest",
    "GateDecision",
    "HealthResponse",
    "DriftResponse",
    "IntentType",
]

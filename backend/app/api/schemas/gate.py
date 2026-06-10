"""Gate API schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.core.models import Language


class GateRequest(BaseModel):
    candidate: str = Field(min_length=1, max_length=200)
    queries: list[str] = Field(min_length=1, max_length=200)
    language: Language = Language.EN


class GateDatasetRequest(BaseModel):
    candidate: str = Field(min_length=1, max_length=200)
    dataset: str = Field(min_length=1, max_length=200)


class GateResponse(BaseModel):
    decision_id: str
    candidate: str
    passed: bool
    aggregate_score: float
    threshold: float
    category_scores: dict[str, float]
    baseline_deltas: dict[str, float]
    regressions: list[str]
    reason: str
    trace_count: int

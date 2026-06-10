"""Ask / evaluation API schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.core.models import Language


class AskRequest(BaseModel):
    text: str = Field(
        min_length=1, max_length=4096, description="Question text. 1-4096 characters."
    )
    language: Language = Language.EN


class TraceIn(BaseModel):
    """Used when submitting pre-recorded traces for batch evaluation."""

    request_text: str = Field(..., min_length=1, max_length=4096)
    response_text: str = Field(..., min_length=1, max_length=16384)
    language: Language = Language.EN


class FindingOut(BaseModel):
    code: str
    message: str
    severity: str
    evidence: dict


class EvalOut(BaseModel):
    evaluator: str
    category: str
    verdict: str
    score: float
    confidence: float
    summary: str
    findings: list[FindingOut]
    duration_ms: float


class AskResponse(BaseModel):
    trace_id: str
    answer: str
    intent: str
    model: str
    latency_ms: float
    aggregate_score: float
    passed: bool
    reason: str
    category_scores: dict[str, float]
    evaluations: list[EvalOut]
    cost: dict
    tool_calls: list[dict]

"""Shared domain models for PitchProof Vigil.

These types flow across the whole system: the concierge agent produces a
ConciergeResponse, the tracer wraps the interaction in a Span/Trace, and the
eval engine emits an EvalResult and ultimately a GateDecision.
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _id() -> str:
    return uuid4().hex


class Language(str, enum.Enum):
    EN = "en"
    ES = "es"
    FR = "fr"
    DE = "de"
    PT = "pt"
    AR = "ar"
    JA = "ja"


class IntentType(str, enum.Enum):
    KICKOFF_TIME = "kickoff_time"
    GATE_INFO = "gate_info"
    TICKETING = "ticketing"
    TRAVEL = "travel"
    STADIUM_NAV = "stadium_nav"
    TRANSLATION = "translation"
    GENERAL = "general"


class ConciergeRequest(BaseModel):
    """Inbound fan query to the World Cup concierge agent."""

    request_id: str = Field(default_factory=_id)
    text: str
    language: Language = Language.EN
    session_id: str = Field(default_factory=_id)
    created_at: datetime = Field(default_factory=_now)


class ConciergeResponse(BaseModel):
    """Agent answer plus the metadata needed to evaluate it."""

    request_id: str
    text: str
    detected_intent: IntentType
    language: Language
    grounded_facts: dict[str, Any] = Field(default_factory=dict)
    latency_ms: float = 0.0
    model: str = "unknown"
    created_at: datetime = Field(default_factory=_now)


class SpanKind(str, enum.Enum):
    AGENT = "AGENT"
    LLM = "LLM"
    TOOL = "TOOL"
    RETRIEVER = "RETRIEVER"
    CHAIN = "CHAIN"


class Span(BaseModel):
    """OpenInference-style span."""

    span_id: str = Field(default_factory=_id)
    trace_id: str
    parent_id: str | None = None
    name: str
    kind: SpanKind
    start_time: datetime = Field(default_factory=_now)
    end_time: datetime | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    status: str = "OK"

    @property
    def duration_ms(self) -> float:
        if self.end_time is None:
            return 0.0
        return (self.end_time - self.start_time).total_seconds() * 1000.0


class Trace(BaseModel):
    """A full agent interaction as a tree of spans."""

    trace_id: str = Field(default_factory=_id)
    request: ConciergeRequest
    response: ConciergeResponse | None = None
    spans: list[Span] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_now)


class EvalVerdict(str, enum.Enum):
    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"


class EvalResult(BaseModel):
    """Outcome of one LLM-as-judge or heuristic evaluator on one trace."""

    eval_id: str = Field(default_factory=_id)
    trace_id: str
    evaluator: str
    verdict: EvalVerdict
    score: float  # 0.0 - 1.0
    explanation: str
    created_at: datetime = Field(default_factory=_now)


class GateDecision(BaseModel):
    """Promotion gate decision for a candidate build/prompt."""

    decision_id: str = Field(default_factory=_id)
    candidate: str
    passed: bool
    aggregate_score: float
    threshold: float
    eval_results: list[EvalResult] = Field(default_factory=list)
    reason: str = ""
    created_at: datetime = Field(default_factory=_now)


class DriftPoint(BaseModel):
    """A single drift measurement over a time window."""

    window_start: datetime
    window_end: datetime
    intent: IntentType
    language: Language
    embedding_distance: float
    sample_count: int

"""Tests for app.core.models."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.core.models import (
    ConciergeRequest,
    ConciergeResponse,
    DriftPoint,
    EvalResult,
    EvalVerdict,
    GateDecision,
    IntentType,
    Language,
    Span,
    SpanKind,
    Trace,
)


def test_request_defaults():
    r = ConciergeRequest(text="hi")
    assert r.language == Language.EN
    assert r.request_id
    assert r.session_id
    assert isinstance(r.created_at, datetime)


def test_span_duration_with_end():
    start = datetime.now(timezone.utc)
    span = Span(
        trace_id="t",
        name="n",
        kind=SpanKind.LLM,
        start_time=start,
        end_time=start + timedelta(milliseconds=250),
    )
    assert abs(span.duration_ms - 250.0) < 1.0


def test_span_duration_without_end():
    span = Span(trace_id="t", name="n", kind=SpanKind.AGENT)
    assert span.duration_ms == 0.0


def test_trace_holds_spans():
    req = ConciergeRequest(text="hi")
    trace = Trace(request=req)
    trace.spans.append(Span(trace_id=trace.trace_id, name="x", kind=SpanKind.TOOL))
    assert len(trace.spans) == 1


def test_eval_and_gate_models():
    er = EvalResult(
        trace_id="t",
        evaluator="e",
        verdict=EvalVerdict.PASS,
        score=1.0,
        explanation="ok",
    )
    gd = GateDecision(
        candidate="c",
        passed=True,
        aggregate_score=1.0,
        threshold=0.85,
        eval_results=[er],
    )
    assert gd.passed and gd.eval_results[0].verdict == EvalVerdict.PASS


def test_response_and_drift_models():
    resp = ConciergeResponse(
        request_id="r",
        text="t",
        detected_intent=IntentType.GENERAL,
        language=Language.FR,
    )
    assert resp.latency_ms == 0.0
    dp = DriftPoint(
        window_start=datetime.now(timezone.utc),
        window_end=datetime.now(timezone.utc),
        intent=IntentType.TRANSLATION,
        language=Language.AR,
        embedding_distance=0.1,
        sample_count=5,
    )
    assert dp.sample_count == 5

"""Tests for the evaluator framework base classes and registry."""
from __future__ import annotations

import pytest

from app.core.models import ConciergeRequest, ConciergeResponse, IntentType, Language, Trace
from app.evaluators.base import (
    EvalContext,
    Evaluator,
    EvaluatorCategory,
    EvaluatorRegistry,
    EvaluatorSpec,
    Finding,
    Severity,
    Verdict,
)


def _trace(text="ok", intent=IntentType.GENERAL, grounded=None, lang=Language.EN, latency=1.0):
    req = ConciergeRequest(text="q", language=lang)
    resp = ConciergeResponse(
        request_id=req.request_id,
        text=text,
        detected_intent=intent,
        language=lang,
        grounded_facts=grounded or {},
        latency_ms=latency,
    )
    return Trace(request=req, response=resp)


class _PassEvaluator(Evaluator):
    spec = EvaluatorSpec(
        name="dummy_pass",
        version="1.0.0",
        category=EvaluatorCategory.QUALITY,
        title="Dummy",
        description="always pass",
    )

    def _run(self, ctx):
        return self._outcome(Verdict.PASS, 1.0, "ok", findings=[
            Finding("c", "m", Severity.LOW)
        ])


class _BoomEvaluator(Evaluator):
    spec = EvaluatorSpec(
        name="dummy_boom",
        version="1.0.0",
        category=EvaluatorCategory.SAFETY,
        title="Boom",
        description="raises",
    )

    def _run(self, ctx):
        raise RuntimeError("kaboom")


def test_verdict_is_blocking():
    assert Verdict.FAIL.is_blocking
    assert Verdict.ERROR.is_blocking
    assert not Verdict.PASS.is_blocking
    assert not Verdict.WARN.is_blocking
    assert not Verdict.SKIP.is_blocking


def test_outcome_weighted_score_and_severity():
    ev = _PassEvaluator()
    out = ev.evaluate(EvalContext(trace=_trace()))
    assert out.weighted_score == 1.0
    assert out.highest_severity() == Severity.LOW
    assert out.duration_ms >= 0.0


def test_outcome_severity_empty_findings():
    ev = _PassEvaluator()
    out = ev._outcome(Verdict.PASS, 1.0, "x")
    assert out.highest_severity() == Severity.INFO


def test_evaluator_error_isolation():
    ev = _BoomEvaluator()
    out = ev.evaluate(EvalContext(trace=_trace()))
    assert out.verdict == Verdict.ERROR
    assert "kaboom" in out.summary
    assert out.findings[0].code == "evaluator_exception"


def test_registry_register_get_all():
    reg = EvaluatorRegistry()
    ev = _PassEvaluator()
    reg.register(ev)
    assert len(reg) == 1
    assert "dummy_pass" in reg
    assert reg.get("dummy_pass") is ev
    assert ev in reg.all()
    assert reg.specs()[0].name == "dummy_pass"
    assert reg.names() == ["dummy_pass"]


def test_registry_duplicate_raises():
    reg = EvaluatorRegistry()
    reg.register(_PassEvaluator())
    with pytest.raises(ValueError):
        reg.register(_PassEvaluator())


def test_registry_unknown_raises():
    reg = EvaluatorRegistry()
    with pytest.raises(KeyError):
        reg.get("nope")


def test_evalcontext_cfg():
    ctx = EvalContext(trace=_trace(), config={"x": 5})
    assert ctx.cfg("x") == 5
    assert ctx.cfg("missing", "default") == "default"

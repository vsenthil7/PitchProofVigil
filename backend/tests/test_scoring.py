"""Tests for the scoring engine, policies, and candidate gate."""
from __future__ import annotations

from app.core.config import Settings
from app.core.models import (
    ConciergeRequest,
    ConciergeResponse,
    IntentType,
    Language,
    Trace,
)
from app.evaluators.base import EvaluatorCategory, Verdict
from app.evaluators.candidate_gate import CandidateGate
from app.evaluators.registry import build_default_registry
from app.evaluators.scoring import (
    EvaluatorPolicy,
    GatePolicy,
    ScoringEngine,
)


def _trace(text="A complete answer.", intent=IntentType.TICKETING, grounded=None, kickoff=None):
    req = ConciergeRequest(text="q")
    gf = grounded if grounded is not None else {}
    if kickoff:
        gf = {"fixture": {"kickoff_local": "2026-06-18T20:00:00"}, "kickoff_local": kickoff}
        intent = IntentType.KICKOFF_TIME
    resp = ConciergeResponse(
        request_id=req.request_id,
        text=text,
        detected_intent=intent,
        language=Language.EN,
        grounded_facts=gf,
        latency_ms=10.0,
    )
    return Trace(request=req, response=resp)


def _engine():
    return ScoringEngine(build_default_registry(Settings(use_mocks=True)))


def test_policy_from_registry():
    reg = build_default_registry(Settings(use_mocks=True))
    pol = GatePolicy.from_registry(reg, name="p", threshold=0.9)
    assert pol.name == "p" and pol.threshold == 0.9
    assert len(pol.evaluator_policies) == len(reg)


def test_policy_for_default():
    pol = GatePolicy()
    p = pol.policy_for("unknown")
    assert p.name == "unknown" and p.enabled


def test_score_trace_clean_passes():
    engine = _engine()
    pol = GatePolicy.from_registry(engine.registry, threshold=0.7)
    report = engine.score_trace(_trace(), pol)
    assert report.passed
    assert "no blocking" in report.reason
    assert report.by_category()
    assert report.verdict_counts()


def test_score_trace_blocking_fail():
    engine = _engine()
    pol = GatePolicy.from_registry(engine.registry, threshold=0.5)
    report = engine.score_trace(_trace(kickoff="2026-06-18T18:00:00"), pol)
    assert not report.passed
    assert "blocking failure" in report.reason
    assert any(o.evaluator == "factual_accuracy" for o in report.blocking_failures())


def test_score_trace_below_threshold_no_block():
    engine = _engine()
    # Disable blocking evaluators, set impossibly high threshold.
    pol = GatePolicy.from_registry(engine.registry, threshold=0.999)
    for name in ("factual_accuracy", "groundedness", "pii_leakage", "unsafe_content"):
        pol.evaluator_policies[name].blocking = False
    # A non-answer drives quality scores down.
    report = engine.score_trace(_trace(text="I don't have", intent=IntentType.GENERAL), pol)
    assert not report.passed
    assert "threshold" in report.reason


def test_disabled_evaluator_skipped():
    engine = _engine()
    pol = GatePolicy.from_registry(engine.registry, threshold=0.5)
    pol.evaluator_policies["llm_judge"].enabled = False
    report = engine.score_trace(_trace(), pol)
    assert all(s.outcome.evaluator != "llm_judge" for s in report.scored)


def test_weight_override():
    engine = _engine()
    pol = GatePolicy.from_registry(engine.registry, threshold=0.5)
    pol.evaluator_policies["latency_slo"].weight = 9.9
    report = engine.score_trace(_trace(), pol)
    slo = next(s for s in report.scored if s.outcome.evaluator == "latency_slo")
    assert slo.weight == 9.9


def test_aggregate_empty_when_all_disabled():
    engine = _engine()
    pol = GatePolicy(name="empty", threshold=0.5, evaluator_policies={
        s.name: EvaluatorPolicy(name=s.name, enabled=False) for s in engine.registry.specs()
    })
    report = engine.score_trace(_trace(), pol)
    assert report.aggregate_score == 0.0


def test_candidate_gate_promote():
    engine = _engine()
    pol = GatePolicy.from_registry(engine.registry, threshold=0.6)
    gate = CandidateGate(engine)
    traces = [_trace(), _trace(text="Another fine grounded answer.", grounded={"x": 1})]
    result = gate.evaluate("v1", traces, pol)
    assert result.passed
    assert result.total_traces() == 2
    assert "PROMOTE" in result.reason


def test_candidate_gate_block_on_failure():
    engine = _engine()
    pol = GatePolicy.from_registry(engine.registry, threshold=0.5)
    gate = CandidateGate(engine)
    traces = [_trace(kickoff="2026-06-18T18:00:00")]
    result = gate.evaluate("v2", traces, pol)
    assert not result.passed
    assert result.blocking_failure_count() == 1
    assert "BLOCK" in result.reason


def test_candidate_gate_baseline_regression():
    engine = _engine()
    pol = GatePolicy.from_registry(engine.registry, threshold=0.5)
    # Disable blocking so only the baseline-regression path triggers the block.
    pol.evaluator_policies["factual_accuracy"].blocking = False
    gate = CandidateGate(engine, regression_tolerance=0.05)
    traces = [_trace(kickoff="2026-06-18T18:00:00")]
    baseline = {"correctness": 1.0}
    result = gate.evaluate("v2", traces, pol, baseline_category_scores=baseline)
    assert not result.passed
    assert result.regressions
    assert result.baseline_deltas["correctness"] < 0


def test_candidate_gate_empty_traces():
    engine = _engine()
    pol = GatePolicy.from_registry(engine.registry, threshold=0.5)
    gate = CandidateGate(engine)
    result = gate.evaluate("empty", [], pol)
    assert result.aggregate_score == 0.0
    assert not result.passed


def test_candidate_gate_with_ground_truths():
    engine = _engine()
    pol = GatePolicy.from_registry(engine.registry, threshold=0.6)
    gate = CandidateGate(engine)
    traces = [_trace(), _trace()]
    gts = [{"a": 1}, {"b": 2}]
    result = gate.evaluate("v1", traces, pol, ground_truths=gts)
    assert result.total_traces() == 2

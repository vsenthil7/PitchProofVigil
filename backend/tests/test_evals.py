"""Tests for app.evals — evaluators, engine, gate, drift."""
from __future__ import annotations

from app.agent.concierge import ConciergeAgent
from app.core.config import Settings
from app.core.models import (
    ConciergeRequest,
    ConciergeResponse,
    IntentType,
    Language,
    Trace,
)
from app.evals.engine import (
    EvalEngine,
    FactualAccuracyEvaluator,
    GroundednessEvaluator,
    TranslationQualityEvaluator,
)
from app.evals.gate import DriftDetector, RegressionGate


def _trace(resp: ConciergeResponse) -> Trace:
    return Trace(request=ConciergeRequest(text="q"), response=resp)


def _resp(**kw) -> ConciergeResponse:
    base = dict(
        request_id="r",
        text="t",
        detected_intent=IntentType.GENERAL,
        language=Language.EN,
        grounded_facts={},
    )
    base.update(kw)
    return ConciergeResponse(**base)


# ---- FactualAccuracyEvaluator ----

def test_factual_pass_when_kickoff_matches():
    fixture = {"kickoff_local": "2026-06-18T20:00:00"}
    resp = _resp(
        detected_intent=IntentType.KICKOFF_TIME,
        grounded_facts={"fixture": fixture, "kickoff_local": "2026-06-18T20:00:00"},
    )
    r = FactualAccuracyEvaluator().evaluate(_trace(resp))
    assert r.verdict.value == "pass"


def test_factual_fail_when_kickoff_mismatch():
    fixture = {"kickoff_local": "2026-06-18T20:00:00"}
    resp = _resp(
        detected_intent=IntentType.KICKOFF_TIME,
        grounded_facts={"fixture": fixture, "kickoff_local": "2026-06-18T18:00:00"},
    )
    r = FactualAccuracyEvaluator().evaluate(_trace(resp))
    assert r.verdict.value == "fail"
    assert r.score == 0.0


def test_factual_warn_when_no_fixture():
    resp = _resp(detected_intent=IntentType.KICKOFF_TIME, grounded_facts={})
    r = FactualAccuracyEvaluator().evaluate(_trace(resp))
    assert r.verdict.value == "warn"


def test_factual_pass_for_non_kickoff():
    resp = _resp(detected_intent=IntentType.TICKETING)
    r = FactualAccuracyEvaluator().evaluate(_trace(resp))
    assert r.verdict.value == "pass"


# ---- GroundednessEvaluator ----

def test_groundedness_fail_when_unsupported_factual():
    resp = _resp(detected_intent=IntentType.GATE_INFO, grounded_facts={})
    r = GroundednessEvaluator().evaluate(_trace(resp))
    assert r.verdict.value == "fail"


def test_groundedness_pass_when_grounded():
    resp = _resp(detected_intent=IntentType.GATE_INFO, grounded_facts={"x": 1})
    r = GroundednessEvaluator().evaluate(_trace(resp))
    assert r.verdict.value == "pass"


def test_groundedness_pass_for_non_factual():
    resp = _resp(detected_intent=IntentType.GENERAL, grounded_facts={})
    r = GroundednessEvaluator().evaluate(_trace(resp))
    assert r.verdict.value == "pass"


# ---- TranslationQualityEvaluator ----

def test_translation_pass_for_english():
    resp = _resp(language=Language.EN)
    r = TranslationQualityEvaluator().evaluate(_trace(resp))
    assert r.verdict.value == "pass"


def test_translation_warn_when_missing_phrase():
    resp = _resp(
        detected_intent=IntentType.GATE_INFO,
        language=Language.ES,
        text="something with no expected phrase",
    )
    r = TranslationQualityEvaluator().evaluate(_trace(resp))
    assert r.verdict.value == "warn"


def test_translation_pass_when_phrase_present():
    resp = _resp(
        detected_intent=IntentType.KICKOFF_TIME,
        language=Language.ES,
        text="El saque inicial es a las 20:00",
    )
    r = TranslationQualityEvaluator().evaluate(_trace(resp))
    assert r.verdict.value == "pass"


def test_translation_pass_when_no_expected_mapping():
    resp = _resp(
        detected_intent=IntentType.TICKETING,
        language=Language.FR,
        text="anything",
    )
    r = TranslationQualityEvaluator().evaluate(_trace(resp))
    assert r.verdict.value == "pass"


# ---- EvalEngine ----

def test_engine_runs_all_and_aggregates():
    engine = EvalEngine(Settings(use_mocks=True))
    resp = _resp(detected_intent=IntentType.TICKETING)
    results = engine.evaluate_trace(_trace(resp))
    assert len(results) == 3
    assert engine.aggregate_score(results) == 1.0


def test_engine_aggregate_empty():
    engine = EvalEngine(Settings(use_mocks=True))
    assert engine.aggregate_score([]) == 0.0


# ---- RegressionGate ----

def _golden_traces(poison: bool):
    agent = ConciergeAgent(Settings(use_mocks=True))
    queries = ["When does France play England?", "buy a ticket"]
    if poison:
        queries.append("When does Spain play Germany?")
    traces = []
    for q in queries:
        req = ConciergeRequest(text=q)
        traces.append(Trace(request=req, response=agent.answer(req)))
    return traces


def test_gate_passes_clean_candidate():
    gate = RegressionGate(settings=Settings(use_mocks=True))
    decision = gate.evaluate_candidate("clean", _golden_traces(poison=False))
    assert decision.passed is True
    assert "no hard failures" in decision.reason


def test_gate_blocks_on_hard_fail():
    gate = RegressionGate(settings=Settings(use_mocks=True))
    decision = gate.evaluate_candidate("poisoned", _golden_traces(poison=True))
    assert decision.passed is False
    assert "hard failure" in decision.reason


def test_gate_blocks_on_low_aggregate_without_hard_fail():
    # Scenario with no hard fail but aggregate below a very high threshold.
    # Spanish kickoff answer that is factually grounded (PASS) and grounded
    # (PASS) but missing the localized phrase (translation WARN, 0.6).
    gate = RegressionGate(settings=Settings(use_mocks=True, regression_threshold=0.99))
    req = ConciergeRequest(text="When does Spain play Germany?", language=Language.ES)
    fixture = {"kickoff_local": "2026-06-18T20:00:00"}
    resp = _resp(
        language=Language.ES,
        detected_intent=IntentType.KICKOFF_TIME,
        text="Kickoff a las 20:00",  # English-ish, missing the ES phrase
        grounded_facts={"fixture": fixture, "kickoff_local": "2026-06-18T20:00:00"},
    )
    decision = gate.evaluate_candidate("warnish", [Trace(request=req, response=resp)])
    assert decision.passed is False
    assert "threshold" in decision.reason
    # Confirm there was genuinely no hard failure driving the block.
    assert all(r.verdict.value != "fail" for r in decision.eval_results)


def test_gate_empty_traces():
    gate = RegressionGate(settings=Settings(use_mocks=True))
    decision = gate.evaluate_candidate("empty", [])
    assert decision.passed is False
    assert decision.aggregate_score == 0.0


# ---- DriftDetector ----

def test_drift_zero_for_small_sample():
    d = DriftDetector(Settings(use_mocks=True))
    point = d.compute([])
    assert point.embedding_distance == 0.0
    assert d.is_alerting(point) is False


def test_drift_single_trace_zero():
    d = DriftDetector(Settings(use_mocks=True))
    resp = _resp(text="hello")
    point = d.compute([_trace(resp)])
    assert point.embedding_distance == 0.0


def test_drift_nonzero_and_alert():
    d = DriftDetector(Settings(use_mocks=True))
    traces = [
        _trace(_resp(text="short")),
        _trace(_resp(text="a very much longer response than the other one" * 3)),
    ]
    point = d.compute(traces, intent=IntentType.KICKOFF_TIME, language=Language.ES)
    assert point.embedding_distance > 0.0
    assert d.is_alerting(point) is True


def test_drift_all_zero_length_mean(monkeypatch):
    d = DriftDetector(Settings(use_mocks=True))
    traces = [_trace(_resp(text="")), _trace(_resp(text=""))]
    point = d.compute(traces)
    assert point.embedding_distance == 0.0


def test_drift_traces_without_responses():
    # Two traces but fewer than two carry a response → distance 0.
    d = DriftDetector(Settings(use_mocks=True))
    with_resp = _trace(_resp(text="hello there"))
    without_resp = Trace(request=ConciergeRequest(text="q"), response=None)
    point = d.compute([with_resp, without_resp])
    assert point.embedding_distance == 0.0

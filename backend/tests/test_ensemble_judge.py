"""Tests for EnsembleJudge multi-model aggregation (P6.M6)."""
from __future__ import annotations

from app.core.config import Settings
from app.core.models import ConciergeRequest, ConciergeResponse, IntentType, Language
from app.evaluators.base import (
    EvalContext,
    EvaluationOutcome,
    EvaluatorCategory,
    Verdict,
)
from app.evaluators.ensemble_judge import EnsembleJudge
from app.phoenix.tracer import Tracer


def _make_ctx(question="When does Spain play?", answer="At 20:00.", config=None):
    req = ConciergeRequest(text=question, language=Language.EN)
    resp = ConciergeResponse(
        request_id=req.request_id, text=answer,
        detected_intent=IntentType.KICKOFF_TIME, language=Language.EN, model="mock",
    )
    trace = Tracer().record(req, resp)
    return EvalContext(trace=trace, config=config or {})


class _StubJudge:
    """Minimal judge whose _run returns a fixed outcome."""

    def __init__(self, score: float, verdict: Verdict):
        self._score = score
        self._verdict = verdict

    def _run(self, ctx) -> EvaluationOutcome:
        return EvaluationOutcome(
            evaluator="llm_judge", version="2.0.0",
            category=EvaluatorCategory.QUALITY, verdict=self._verdict,
            score=self._score, confidence=0.9, summary=f"score={self._score}",
        )


def _ensemble(aggregation, judge_specs):
    ens = EnsembleJudge(
        model_ids=[f"m{i}" for i in range(len(judge_specs))],
        aggregation=aggregation, settings=Settings(use_mocks=True),
    )
    ens.judges = [_StubJudge(s, v) for s, v in judge_specs]
    return ens


def test_ensemble_majority_pass_pass_fail_gives_pass():
    ens = _ensemble("majority", [(0.8, Verdict.PASS), (0.75, Verdict.PASS), (0.4, Verdict.FAIL)])
    out = ens._run(_make_ctx())
    assert out.verdict == Verdict.PASS


def test_ensemble_mean_low_score_fails():
    ens = _ensemble("mean", [(0.3, Verdict.FAIL), (0.4, Verdict.FAIL), (0.35, Verdict.FAIL)])
    out = ens._run(_make_ctx())
    assert out.verdict == Verdict.FAIL
    assert out.metadata["model_count"] == 3
    # FAIL verdict produces a finding.
    assert any(f.code == "ensemble_low_score" for f in out.findings)


def test_ensemble_mean_mid_score_warns():
    # fail_below=2.5/4=0.625, warn_below=3.5/4=0.875; mean 0.7 -> WARN
    ens = _ensemble("mean", [(0.7, Verdict.WARN), (0.7, Verdict.WARN)])
    out = ens._run(_make_ctx())
    assert out.verdict == Verdict.WARN


def test_ensemble_mean_high_score_passes_no_findings():
    ens = _ensemble("mean", [(0.9, Verdict.PASS), (0.95, Verdict.PASS)])
    out = ens._run(_make_ctx())
    assert out.verdict == Verdict.PASS
    assert out.findings == []
    assert len(out.metadata["individual_scores"]) == 2
    assert out.metadata["aggregation"] == "mean"


def test_ensemble_respects_custom_thresholds():
    # With fail_below=4.0 (->1.0 normalized), even 0.9 mean fails.
    ens = _ensemble("mean", [(0.9, Verdict.PASS), (0.9, Verdict.PASS)])
    out = ens._run(_make_ctx(config={"fail_below": 4.0}))
    assert out.verdict == Verdict.FAIL


def test_ensemble_default_models_from_settings():
    """No model_ids -> parsed from settings.judge_models."""
    s = Settings(use_mocks=True, judge_models="gemini-2.0-flash,gemini-1.5-pro")
    ens = EnsembleJudge(settings=s)
    assert len(ens.judges) == 2

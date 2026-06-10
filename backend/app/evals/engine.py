"""Evaluation engine — LLM-as-judge + heuristic evaluators over traces.

Each evaluator takes a Trace and returns an EvalResult (verdict + score +
explanation). Real mode uses Gemini as the judge model; mock mode uses
deterministic heuristics that check responses against the authoritative
fixture data. The mock judge is intentionally good enough to catch the
poisoned-kickoff regression injected by the mock concierge.
"""
from __future__ import annotations

from app.agent import fixtures
from app.core.config import Settings, get_settings
from app.core.models import (
    EvalResult,
    EvalVerdict,
    IntentType,
    Trace,
)


class BaseEvaluator:
    name: str = "base"

    def evaluate(self, trace: Trace) -> EvalResult:  # pragma: no cover - abstract
        raise NotImplementedError


class FactualAccuracyEvaluator(BaseEvaluator):
    """Checks the response against authoritative fixture facts.

    For kickoff-time answers, the canonical kickoff is compared to the time the
    agent actually stated (via grounded_facts). A mismatch is a hard FAIL —
    this is the evaluator that catches the silent two-hour regression.
    """

    name = "factual_accuracy"

    def evaluate(self, trace: Trace) -> EvalResult:
        resp = trace.response
        assert resp is not None
        verdict = EvalVerdict.PASS
        score = 1.0
        explanation = "Response consistent with authoritative data."

        if resp.detected_intent == IntentType.KICKOFF_TIME:
            fixture = resp.grounded_facts.get("fixture")
            stated = resp.grounded_facts.get("kickoff_local")
            if fixture and stated and stated != fixture["kickoff_local"]:
                verdict = EvalVerdict.FAIL
                score = 0.0
                explanation = (
                    f"Kickoff mismatch: stated {stated} but authoritative is "
                    f"{fixture['kickoff_local']}."
                )
            elif not fixture:
                verdict = EvalVerdict.WARN
                score = 0.5
                explanation = "Kickoff intent but no fixture grounded."

        return EvalResult(
            trace_id=trace.trace_id,
            evaluator=self.name,
            verdict=verdict,
            score=score,
            explanation=explanation,
        )


class GroundednessEvaluator(BaseEvaluator):
    """Flags responses that make claims without any grounded facts."""

    name = "groundedness"

    HALLUCINATION_RISK = {
        IntentType.KICKOFF_TIME,
        IntentType.GATE_INFO,
        IntentType.TRAVEL,
    }

    def evaluate(self, trace: Trace) -> EvalResult:
        resp = trace.response
        assert resp is not None
        if resp.detected_intent in self.HALLUCINATION_RISK and not resp.grounded_facts:
            return EvalResult(
                trace_id=trace.trace_id,
                evaluator=self.name,
                verdict=EvalVerdict.FAIL,
                score=0.0,
                explanation="Fact-bearing answer with no grounding — hallucination risk.",
            )
        return EvalResult(
            trace_id=trace.trace_id,
            evaluator=self.name,
            verdict=EvalVerdict.PASS,
            score=1.0,
            explanation="Answer is grounded or non-factual.",
        )


class TranslationQualityEvaluator(BaseEvaluator):
    """Checks non-English answers use the expected localized phrasing."""

    name = "translation_quality"

    def evaluate(self, trace: Trace) -> EvalResult:
        resp = trace.response
        assert resp is not None
        lang = resp.language.value
        if lang == "en":
            return EvalResult(
                trace_id=trace.trace_id,
                evaluator=self.name,
                verdict=EvalVerdict.PASS,
                score=1.0,
                explanation="English response; no translation check required.",
            )
        expected = None
        if resp.detected_intent == IntentType.GATE_INFO:
            expected = fixtures.TRANSLATIONS["where_is_my_gate"].get(lang)
        elif resp.detected_intent == IntentType.KICKOFF_TIME:
            expected = fixtures.TRANSLATIONS["kickoff_is_at"].get(lang)

        if expected and expected.lower() not in resp.text.lower():
            return EvalResult(
                trace_id=trace.trace_id,
                evaluator=self.name,
                verdict=EvalVerdict.WARN,
                score=0.6,
                explanation=f"Expected localized phrase '{expected}' not found.",
            )
        return EvalResult(
            trace_id=trace.trace_id,
            evaluator=self.name,
            verdict=EvalVerdict.PASS,
            score=1.0,
            explanation="Translation phrasing acceptable.",
        )


class EvalEngine:
    """Runs all evaluators over a trace and aggregates results."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.mode = self.settings.integration_mode("gemini")
        self.evaluators: list[BaseEvaluator] = [
            FactualAccuracyEvaluator(),
            GroundednessEvaluator(),
            TranslationQualityEvaluator(),
        ]

    def evaluate_trace(self, trace: Trace) -> list[EvalResult]:
        return [e.evaluate(trace) for e in self.evaluators]

    def aggregate_score(self, results: list[EvalResult]) -> float:
        if not results:
            return 0.0
        return sum(r.score for r in results) / len(results)

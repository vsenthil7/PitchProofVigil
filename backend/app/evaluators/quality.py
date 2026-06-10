"""Quality, performance, and translation evaluators."""
from __future__ import annotations

from app.agent import fixtures
from app.core.models import IntentType
from app.evaluators.base import (
    EvalContext,
    Evaluator,
    EvaluatorCategory,
    EvaluatorConfigField,
    EvaluatorSpec,
    EvaluationOutcome,
    Finding,
    Severity,
    Verdict,
)


class TranslationQualityEvaluator(Evaluator):
    """Checks non-English answers use expected localized phrasing."""

    spec = EvaluatorSpec(
        name="translation_quality",
        version="2.0.0",
        category=EvaluatorCategory.QUALITY,
        title="Translation Quality",
        description="Verifies localized phrasing for non-English answers.",
        default_weight=1.0,
        blocking_by_default=False,
    )

    def _run(self, ctx: EvalContext) -> EvaluationOutcome:
        resp = ctx.trace.response
        if resp is None:
            return self._outcome(Verdict.ERROR, 0.0, "No response on trace.")
        lang = resp.language.value
        if lang == "en":
            return self._outcome(Verdict.SKIP, 1.0, "English answer; no check.")

        expected = None
        if resp.detected_intent == IntentType.GATE_INFO:
            expected = fixtures.TRANSLATIONS["where_is_my_gate"].get(lang)
        elif resp.detected_intent == IntentType.KICKOFF_TIME:
            expected = fixtures.TRANSLATIONS["kickoff_is_at"].get(lang)

        if expected and expected.lower() not in resp.text.lower():
            return self._outcome(
                Verdict.WARN,
                0.6,
                f"Expected localized phrase '{expected}' missing.",
                confidence=0.8,
                findings=[
                    Finding(
                        "localization_gap",
                        f"Answer in '{lang}' lacks expected phrase.",
                        Severity.MEDIUM,
                        evidence={"expected_phrase": expected, "lang": lang},
                    )
                ],
            )
        return self._outcome(Verdict.PASS, 1.0, "Localized phrasing acceptable.")


class ResponseCompletenessEvaluator(Evaluator):
    """Penalizes empty, truncated, or non-answer responses."""

    spec = EvaluatorSpec(
        name="response_completeness",
        version="1.0.0",
        category=EvaluatorCategory.QUALITY,
        title="Response Completeness",
        description="Flags empty, too-short, or evasive answers.",
        default_weight=1.0,
        blocking_by_default=False,
        config_fields=(
            EvaluatorConfigField(
                name="min_chars",
                type="int",
                default=10,
                description="Minimum acceptable answer length.",
                minimum=1,
                maximum=500,
            ),
        ),
    )

    NON_ANSWERS = ("i don't have", "i'm sorry", "i cannot", "no information")

    def _run(self, ctx: EvalContext) -> EvaluationOutcome:
        resp = ctx.trace.response
        if resp is None:
            return self._outcome(Verdict.ERROR, 0.0, "No response on trace.")
        text = resp.text.strip()
        min_chars = int(ctx.cfg("min_chars", 10))
        if len(text) < min_chars:
            return self._outcome(
                Verdict.WARN,
                0.3,
                f"Answer shorter than {min_chars} chars.",
                findings=[Finding("too_short", "Answer is very short.", Severity.LOW)],
            )
        low = text.lower()
        if any(p in low for p in self.NON_ANSWERS):
            return self._outcome(
                Verdict.WARN,
                0.5,
                "Answer appears evasive / non-committal.",
                confidence=0.6,
                findings=[
                    Finding("non_answer", "Detected non-answer phrasing.", Severity.LOW)
                ],
            )
        return self._outcome(Verdict.PASS, 1.0, "Answer is complete.")


class LatencySLOEvaluator(Evaluator):
    """Enforces a latency budget on the agent response."""

    spec = EvaluatorSpec(
        name="latency_slo",
        version="1.0.0",
        category=EvaluatorCategory.PERFORMANCE,
        title="Latency SLO",
        description="Checks response latency against a configurable budget.",
        default_weight=0.5,
        blocking_by_default=False,
        config_fields=(
            EvaluatorConfigField(
                name="budget_ms",
                type="float",
                default=2000.0,
                description="Latency budget in milliseconds.",
                minimum=1.0,
                maximum=60000.0,
            ),
        ),
    )

    def _run(self, ctx: EvalContext) -> EvaluationOutcome:
        resp = ctx.trace.response
        if resp is None:
            return self._outcome(Verdict.ERROR, 0.0, "No response on trace.")
        budget = float(ctx.cfg("budget_ms", 2000.0))
        latency = resp.latency_ms
        if latency > budget:
            ratio = latency / budget if budget else float("inf")
            return self._outcome(
                Verdict.WARN if ratio < 2 else Verdict.FAIL,
                max(0.0, 1.0 - (ratio - 1.0)),
                f"Latency {latency:.0f}ms over budget {budget:.0f}ms.",
                findings=[
                    Finding(
                        "slo_breach",
                        "Response exceeded latency budget.",
                        Severity.MEDIUM if ratio < 2 else Severity.HIGH,
                        evidence={"latency_ms": latency, "budget_ms": budget},
                    )
                ],
            )
        return self._outcome(
            Verdict.PASS, 1.0, f"Latency {latency:.0f}ms within budget."
        )


class IntentResolutionEvaluator(Evaluator):
    """Flags answers that resolved to GENERAL intent (catch-all = likely miss)."""

    spec = EvaluatorSpec(
        name="intent_resolution",
        version="1.0.0",
        category=EvaluatorCategory.QUALITY,
        title="Intent Resolution",
        description="Detects fall-through to the GENERAL catch-all intent.",
        default_weight=0.5,
        blocking_by_default=False,
    )

    def _run(self, ctx: EvalContext) -> EvaluationOutcome:
        resp = ctx.trace.response
        if resp is None:
            return self._outcome(Verdict.ERROR, 0.0, "No response on trace.")
        if resp.detected_intent == IntentType.GENERAL:
            return self._outcome(
                Verdict.WARN,
                0.5,
                "Query fell through to GENERAL intent.",
                confidence=0.6,
                findings=[
                    Finding(
                        "intent_fallthrough",
                        "No specific intent matched.",
                        Severity.LOW,
                    )
                ],
            )
        return self._outcome(Verdict.PASS, 1.0, "Specific intent resolved.")

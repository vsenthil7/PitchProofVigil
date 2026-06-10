"""Groundedness evaluator."""
from __future__ import annotations


from app.core.models import IntentType
from app.evaluators.base import (
    EvalContext,
    Evaluator,
    EvaluatorCategory,
    EvaluatorSpec,
    EvaluationOutcome,
    Finding,
    Severity,
    Verdict,
)


class GroundednessEvaluator(Evaluator):
    """Detects fact-bearing answers that cite no supporting context."""

    spec = EvaluatorSpec(
        name="groundedness",
        version="2.0.0",
        category=EvaluatorCategory.GROUNDING,
        title="Groundedness",
        description=(
            "Flags answers that assert facts (times, gates, travel) without "
            "any retrieved grounding — a hallucination risk."
        ),
        default_weight=1.5,
        blocking_by_default=True,
    )

    FACT_BEARING = {
        IntentType.KICKOFF_TIME,
        IntentType.GATE_INFO,
        IntentType.TRAVEL,
        IntentType.STADIUM_NAV,
    }

    def _run(self, ctx: EvalContext) -> EvaluationOutcome:
        resp = ctx.trace.response
        if resp is None:
            return self._outcome(Verdict.ERROR, 0.0, "No response on trace.")
        if resp.detected_intent not in self.FACT_BEARING:
            return self._outcome(
                Verdict.PASS, 1.0, "Non-factual intent; grounding not required."
            )
        if not resp.grounded_facts:
            return self._outcome(
                Verdict.FAIL,
                0.0,
                "Fact-bearing answer with zero grounding.",
                findings=[
                    Finding(
                        "ungrounded_claim",
                        "Answer asserts facts but retrieved no context.",
                        Severity.HIGH,
                        evidence={"intent": resp.detected_intent.value},
                    )
                ],
            )
        return self._outcome(
            Verdict.PASS, 1.0, "Fact-bearing answer is grounded in context."
        )

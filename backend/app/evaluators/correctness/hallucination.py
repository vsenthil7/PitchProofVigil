"""Hallucination evaluator."""
from __future__ import annotations


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
from app.evaluators.correctness._shared import _TIME_RE


class HallucinationEvaluator(Evaluator):
    """Flags numbers/times in the answer that don't appear in grounding.

    A lightweight claim-extraction heuristic: any clock time mentioned in the
    answer should be derivable from the grounded facts. Times that appear from
    nowhere are likely fabricated.
    """

    spec = EvaluatorSpec(
        name="hallucination_check",
        version="1.0.0",
        category=EvaluatorCategory.GROUNDING,
        title="Hallucination Check",
        description="Detects clock times in the answer absent from grounding.",
        default_weight=1.0,
        blocking_by_default=False,
    )

    def _run(self, ctx: EvalContext) -> EvaluationOutcome:
        resp = ctx.trace.response
        if resp is None:
            return self._outcome(Verdict.ERROR, 0.0, "No response on trace.")
        times_in_answer = {f"{h}:{m}" for h, m in _TIME_RE.findall(resp.text)}
        if not times_in_answer:
            return self._outcome(Verdict.SKIP, 1.0, "No time claims to verify.")

        grounded_blob = str(resp.grounded_facts)
        unsupported = {
            t for t in times_in_answer if t not in grounded_blob and t.replace(":0", ":") not in grounded_blob
        }
        # Normalize: a grounded ISO time like 20:00:00 supports "20:00".
        unsupported = {
            t for t in times_in_answer
            if t.split(":")[0].zfill(2) + ":" + t.split(":")[1] not in grounded_blob
        }
        if unsupported:
            return self._outcome(
                Verdict.WARN,
                0.4,
                f"Time(s) not found in grounding: {sorted(unsupported)}.",
                confidence=0.6,
                findings=[
                    Finding(
                        "possible_hallucination",
                        "Answer contains clock times absent from grounded facts.",
                        Severity.MEDIUM,
                        evidence={"unsupported_times": sorted(unsupported)},
                    )
                ],
            )
        return self._outcome(
            Verdict.PASS, 1.0, "All time claims trace back to grounding."
        )

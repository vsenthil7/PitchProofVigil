"""Factual-accuracy evaluator."""
from __future__ import annotations

from datetime import datetime

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


class FactualAccuracyEvaluator(Evaluator):
    """Compares stated facts (kickoff time, venue, gate) to ground truth.

    Tolerance on time is configurable; a mismatch beyond tolerance is a hard
    failure with structured evidence describing the delta.
    """

    spec = EvaluatorSpec(
        name="factual_accuracy",
        version="2.0.0",
        category=EvaluatorCategory.CORRECTNESS,
        title="Factual Accuracy",
        description=(
            "Verifies kickoff times, venues and gate numbers against the "
            "authoritative tournament fixture data."
        ),
        default_weight=2.0,
        blocking_by_default=True,
        requires_ground_truth=True,
        config_fields=(
            EvaluatorConfigField(
                name="time_tolerance_minutes",
                type="int",
                default=0,
                description="Allowed deviation in stated kickoff time.",
                minimum=0,
                maximum=120,
            ),
        ),
    )

    def _parse_time(self, value: str) -> datetime | None:
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(value, fmt)
            except (ValueError, TypeError):
                continue
        return None

    def _run(self, ctx: EvalContext) -> EvaluationOutcome:
        resp = ctx.trace.response
        if resp is None:
            return self._outcome(Verdict.ERROR, 0.0, "No response on trace.")

        if resp.detected_intent != IntentType.KICKOFF_TIME:
            return self._outcome(
                Verdict.SKIP, 1.0, "Not a kickoff-time answer; accuracy N/A."
            )

        fixture = resp.grounded_facts.get("fixture")
        stated = resp.grounded_facts.get("kickoff_local")
        if not fixture:
            return self._outcome(
                Verdict.WARN,
                0.5,
                "Kickoff answer without a grounded fixture to verify against.",
                confidence=0.7,
                findings=[
                    Finding(
                        "missing_fixture",
                        "No fixture in grounded_facts.",
                        Severity.MEDIUM,
                    )
                ],
            )

        authoritative = fixture["kickoff_local"]
        tol = int(ctx.cfg("time_tolerance_minutes", 0))
        a_time = self._parse_time(authoritative)
        s_time = self._parse_time(stated) if stated else None

        if a_time and s_time:
            delta_min = abs((a_time - s_time).total_seconds()) / 60.0
            if delta_min > tol:
                return self._outcome(
                    Verdict.FAIL,
                    0.0,
                    f"Kickoff off by {delta_min:.0f} min (stated {stated}, "
                    f"authoritative {authoritative}).",
                    findings=[
                        Finding(
                            "kickoff_mismatch",
                            "Stated kickoff deviates from authoritative time.",
                            Severity.CRITICAL,
                            evidence={
                                "stated": stated,
                                "authoritative": authoritative,
                                "delta_minutes": delta_min,
                                "tolerance_minutes": tol,
                            },
                        )
                    ],
                )
            return self._outcome(
                Verdict.PASS,
                1.0,
                f"Kickoff within tolerance ({delta_min:.0f} ≤ {tol} min).",
            )

        # Fall back to string equality if parsing failed.
        if stated == authoritative:
            return self._outcome(Verdict.PASS, 1.0, "Kickoff matches exactly.")
        return self._outcome(
            Verdict.FAIL,
            0.0,
            f"Kickoff mismatch (stated {stated}, authoritative {authoritative}).",
            findings=[
                Finding(
                    "kickoff_mismatch",
                    "Stated kickoff differs from authoritative value.",
                    Severity.CRITICAL,
                    evidence={"stated": stated, "authoritative": authoritative},
                )
            ],
        )

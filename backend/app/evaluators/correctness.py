"""Correctness and grounding evaluators.

These check the agent's answer against authoritative ground truth and verify
that fact-bearing claims are actually supported by retrieved context.
"""
from __future__ import annotations

import re
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

_TIME_RE = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")


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

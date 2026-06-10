"""Candidate promotion gate with baseline regression comparison.

Runs a candidate (build/prompt) across a golden dataset, scores every trace,
and decides promotion. Beyond a static threshold it supports *baseline
comparison*: if a previous version's per-category scores are supplied, a
material regression against the baseline blocks promotion even when the
absolute threshold is met.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from app.evaluators.scoring import EvaluationReport, GatePolicy, ScoringEngine


@dataclass
class CandidateGateResult:
    decision_id: str
    candidate: str
    policy_name: str
    passed: bool
    aggregate_score: float
    threshold: float
    reports: list[EvaluationReport]
    category_scores: dict[str, float]
    baseline_deltas: dict[str, float]
    regressions: list[str]
    reason: str
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def total_traces(self) -> int:
        return len(self.reports)

    def blocking_failure_count(self) -> int:
        return sum(len(r.blocking_failures()) for r in self.reports)


class CandidateGate:
    """Evaluate a candidate over a golden set and decide promotion."""

    def __init__(
        self, engine: ScoringEngine, regression_tolerance: float = 0.05
    ) -> None:
        self.engine = engine
        self.regression_tolerance = regression_tolerance

    def evaluate(
        self,
        candidate: str,
        traces: list,
        policy: GatePolicy,
        ground_truths: list[dict] | None = None,
        baseline_category_scores: dict[str, float] | None = None,
    ) -> CandidateGateResult:
        reports: list[EvaluationReport] = []
        for i, trace in enumerate(traces):
            gt = (
                ground_truths[i]
                if ground_truths and i < len(ground_truths)
                else {}
            )
            reports.append(self.engine.score_trace(trace, policy, ground_truth=gt))

        aggregate = (
            sum(r.aggregate_score for r in reports) / len(reports) if reports else 0.0
        )
        category_scores = self._mean_category_scores(reports)
        any_blocking = any(r.blocking_failures() for r in reports)
        below_threshold = aggregate < policy.threshold

        baseline_deltas: dict[str, float] = {}
        regressions: list[str] = []
        if baseline_category_scores:
            for cat, base in baseline_category_scores.items():
                now = category_scores.get(cat, 0.0)
                delta = now - base
                baseline_deltas[cat] = delta
                if delta < -self.regression_tolerance:
                    regressions.append(
                        f"{cat}: {now:.2f} vs baseline {base:.2f} "
                        f"(Δ{delta:+.2f})"
                    )

        passed = not any_blocking and not below_threshold and not regressions
        reason = self._reason(
            passed, aggregate, policy, any_blocking, below_threshold, regressions, reports
        )
        return CandidateGateResult(
            decision_id=uuid4().hex,
            candidate=candidate,
            policy_name=policy.name,
            passed=passed,
            aggregate_score=aggregate,
            threshold=policy.threshold,
            reports=reports,
            category_scores=category_scores,
            baseline_deltas=baseline_deltas,
            regressions=regressions,
            reason=reason,
        )

    def _mean_category_scores(
        self, reports: list[EvaluationReport]
    ) -> dict[str, float]:
        acc: dict[str, list[float]] = {}
        for r in reports:
            for cat, val in r.by_category().items():
                acc.setdefault(cat, []).append(val)
        return {c: sum(v) / len(v) for c, v in acc.items()}

    def _reason(
        self,
        passed,
        aggregate,
        policy,
        any_blocking,
        below_threshold,
        regressions,
        reports,
    ) -> str:
        if passed:
            return (
                f"PROMOTE: aggregate {aggregate:.3f} ≥ {policy.threshold:.3f} "
                f"across {len(reports)} trace(s); no blocking failures or "
                f"baseline regressions."
            )
        parts = []
        if any_blocking:
            n = sum(len(r.blocking_failures()) for r in reports)
            first = next(
                (r.blocking_failures()[0] for r in reports if r.blocking_failures()),
                None,
            )
            detail = f" First — {first.evaluator}: {first.summary}" if first else ""
            parts.append(f"{n} blocking failure(s).{detail}")
        if below_threshold:
            parts.append(
                f"aggregate {aggregate:.3f} < threshold {policy.threshold:.3f}."
            )
        if regressions:
            parts.append(f"baseline regression(s): {'; '.join(regressions)}")
        return "BLOCK: " + " ".join(parts)

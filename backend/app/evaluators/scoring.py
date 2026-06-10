"""Evaluation policies and scoring.

A ``GatePolicy`` defines, per evaluator, whether it is enabled, its weight, its
config overrides, and whether it blocks. The ``ScoringEngine`` runs a set of
evaluators over a trace (or many traces) under a policy and produces a rich
``EvaluationReport`` with weighted aggregate, category breakdowns, and a clear
blocking decision.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.evaluators.base import (
    EvalContext,
    Evaluator,
    EvaluatorCategory,
    EvaluatorRegistry,
    EvaluationOutcome,
    Verdict,
)


@dataclass
class EvaluatorPolicy:
    """Per-evaluator policy within a gate."""

    name: str
    enabled: bool = True
    weight: float | None = None  # None → use evaluator default
    blocking: bool | None = None  # None → use evaluator default
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class GatePolicy:
    """A named, versioned set of evaluator policies plus a pass threshold."""

    name: str = "default"
    threshold: float = 0.85
    evaluator_policies: dict[str, EvaluatorPolicy] = field(default_factory=dict)
    fail_on_any_blocking: bool = True

    def policy_for(self, name: str) -> EvaluatorPolicy:
        return self.evaluator_policies.get(name, EvaluatorPolicy(name=name))

    @classmethod
    def from_registry(
        cls, registry: EvaluatorRegistry, name: str = "default", threshold: float = 0.85
    ) -> "GatePolicy":
        """Build a policy enabling every registered evaluator at its defaults."""
        policies = {
            spec.name: EvaluatorPolicy(name=spec.name) for spec in registry.specs()
        }
        return cls(name=name, threshold=threshold, evaluator_policies=policies)


@dataclass
class ScoredOutcome:
    """An evaluator outcome plus the resolved weight/blocking under a policy."""

    outcome: EvaluationOutcome
    weight: float
    blocking: bool

    @property
    def counts_in_aggregate(self) -> bool:
        return self.outcome.verdict not in {Verdict.SKIP, Verdict.ERROR}


@dataclass
class EvaluationReport:
    """The full result of scoring one trace under a policy."""

    trace_id: str
    policy_name: str
    scored: list[ScoredOutcome]
    aggregate_score: float
    passed: bool
    reason: str

    def by_category(self) -> dict[str, float]:
        buckets: dict[str, list[float]] = {}
        for s in self.scored:
            if not s.counts_in_aggregate:
                continue
            cat = s.outcome.category.value
            buckets.setdefault(cat, []).append(s.outcome.weighted_score)
        return {c: sum(v) / len(v) for c, v in buckets.items() if v}

    def blocking_failures(self) -> list[EvaluationOutcome]:
        return [
            s.outcome
            for s in self.scored
            if s.blocking and s.outcome.verdict.is_blocking
        ]

    def verdict_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for s in self.scored:
            v = s.outcome.verdict.value
            counts[v] = counts.get(v, 0) + 1
        return counts


class ScoringEngine:
    """Runs evaluators under a policy and computes the gate decision."""

    def __init__(self, registry: EvaluatorRegistry) -> None:
        self.registry = registry

    def _resolve(
        self, evaluator: Evaluator, pol: EvaluatorPolicy
    ) -> tuple[float, bool]:
        weight = pol.weight if pol.weight is not None else evaluator.spec.default_weight
        blocking = (
            pol.blocking
            if pol.blocking is not None
            else evaluator.spec.blocking_by_default
        )
        return weight, blocking

    def score_trace(
        self,
        trace,
        policy: GatePolicy,
        ground_truth: dict[str, Any] | None = None,
        baseline: dict[str, Any] | None = None,
    ) -> EvaluationReport:
        scored: list[ScoredOutcome] = []
        for evaluator in self.registry.all():
            pol = policy.policy_for(evaluator.spec.name)
            if not pol.enabled:
                continue
            weight, blocking = self._resolve(evaluator, pol)
            ctx = EvalContext(
                trace=trace,
                ground_truth=ground_truth or {},
                config=pol.config,
                baseline=baseline or {},
            )
            outcome = evaluator.evaluate(ctx)
            scored.append(ScoredOutcome(outcome=outcome, weight=weight, blocking=blocking))

        aggregate = self._aggregate(scored)
        blocking_fails = [
            s for s in scored if s.blocking and s.outcome.verdict.is_blocking
        ]
        passed = aggregate >= policy.threshold and not (
            policy.fail_on_any_blocking and blocking_fails
        )
        reason = self._reason(passed, aggregate, policy, blocking_fails)
        return EvaluationReport(
            trace_id=trace.trace_id,
            policy_name=policy.name,
            scored=scored,
            aggregate_score=aggregate,
            passed=passed,
            reason=reason,
        )

    def _aggregate(self, scored: list[ScoredOutcome]) -> float:
        num = 0.0
        den = 0.0
        for s in scored:
            if not s.counts_in_aggregate:
                continue
            num += s.outcome.weighted_score * s.weight
            den += s.weight
        return num / den if den else 0.0

    def _reason(
        self,
        passed: bool,
        aggregate: float,
        policy: GatePolicy,
        blocking_fails: list[ScoredOutcome],
    ) -> str:
        if passed:
            return (
                f"Aggregate {aggregate:.3f} ≥ threshold {policy.threshold:.3f}; "
                f"no blocking failures."
            )
        if blocking_fails:
            first = blocking_fails[0].outcome
            return (
                f"Blocked: {len(blocking_fails)} blocking failure(s). "
                f"First — {first.evaluator}: {first.summary}"
            )
        return f"Blocked: aggregate {aggregate:.3f} < threshold {policy.threshold:.3f}."

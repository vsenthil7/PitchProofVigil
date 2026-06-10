"""Regression gate + drift detection.

The gate runs the eval engine across a candidate's golden dataset and decides
whether the build/prompt may be promoted. This is the "block-on-regression"
step demoed on screen.
"""
from __future__ import annotations

import statistics
from datetime import datetime, timedelta, timezone

from app.core.config import Settings, get_settings
from app.core.models import (
    DriftPoint,
    EvalResult,
    GateDecision,
    IntentType,
    Language,
    Trace,
)
from app.evals.engine import EvalEngine


class RegressionGate:
    """Decide whether a candidate passes based on aggregate eval score."""

    def __init__(
        self, engine: EvalEngine | None = None, settings: Settings | None = None
    ) -> None:
        self.settings = settings or get_settings()
        self.engine = engine or EvalEngine(self.settings)
        self.threshold = self.settings.regression_threshold

    def evaluate_candidate(
        self, candidate: str, traces: list[Trace]
    ) -> GateDecision:
        all_results: list[EvalResult] = []
        for trace in traces:
            all_results.extend(self.engine.evaluate_trace(trace))

        aggregate = self.engine.aggregate_score(all_results) if all_results else 0.0
        has_hard_fail = any(r.verdict.value == "fail" for r in all_results)
        passed = aggregate >= self.threshold and not has_hard_fail

        if passed:
            reason = f"Aggregate {aggregate:.3f} ≥ threshold {self.threshold:.3f}; no hard failures."
        elif has_hard_fail:
            failed = [r for r in all_results if r.verdict.value == "fail"]
            reason = (
                f"Blocked: {len(failed)} hard failure(s). "
                f"First: {failed[0].explanation}"
            )
        else:
            reason = f"Blocked: aggregate {aggregate:.3f} < threshold {self.threshold:.3f}."

        return GateDecision(
            candidate=candidate,
            passed=passed,
            aggregate_score=aggregate,
            threshold=self.threshold,
            eval_results=all_results,
            reason=reason,
        )


class DriftDetector:
    """Computes embedding-distance drift across time windows.

    Mock mode synthesizes distances from response-length variance as a stand-in
    for true multilingual embedding drift; the shape and alerting logic match
    the real Arize AX path.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.alert_threshold = 0.35

    def _pseudo_embedding_distance(self, traces: list[Trace]) -> float:
        if len(traces) < 2:
            return 0.0
        lengths = [len(t.response.text) for t in traces if t.response]
        if len(lengths) < 2:
            return 0.0
        mean = statistics.mean(lengths)
        if mean == 0:
            return 0.0
        return min(statistics.pstdev(lengths) / mean, 1.0)

    def compute(
        self,
        traces: list[Trace],
        intent: IntentType = IntentType.GENERAL,
        language: Language = Language.EN,
        window_minutes: int = 60,
    ) -> DriftPoint:
        now = datetime.now(timezone.utc)
        distance = self._pseudo_embedding_distance(traces)
        return DriftPoint(
            window_start=now - timedelta(minutes=window_minutes),
            window_end=now,
            intent=intent,
            language=language,
            embedding_distance=distance,
            sample_count=len(traces),
        )

    def is_alerting(self, point: DriftPoint) -> bool:
        return point.embedding_distance >= self.alert_threshold

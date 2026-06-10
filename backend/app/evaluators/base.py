"""Evaluator framework — the core abstractions for the eval science layer.

An ``Evaluator`` takes an ``EvalContext`` (the trace plus ground truth and
config) and returns an ``EvaluationOutcome`` (verdict, score, confidence,
structured findings, and timing). Evaluators self-describe via an
``EvaluatorSpec`` so the platform can render config UIs, version them, and
gate on them selectively.

This module deliberately knows nothing about HTTP, the DB, or specific
evaluators — it is the stable contract every concrete evaluator implements.
"""
from __future__ import annotations

import abc
import enum
import time
from dataclasses import dataclass, field
from typing import Any, Iterable

from app.core.models import Trace


class Verdict(str, enum.Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    ERROR = "error"  # evaluator itself failed to run
    SKIP = "skip"  # not applicable to this trace

    @property
    def is_blocking(self) -> bool:
        return self in {Verdict.FAIL, Verdict.ERROR}


class Severity(str, enum.Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EvaluatorCategory(str, enum.Enum):
    CORRECTNESS = "correctness"
    GROUNDING = "grounding"
    SAFETY = "safety"
    QUALITY = "quality"
    PERFORMANCE = "performance"
    COMPLIANCE = "compliance"
    SCHEMA = "schema"


@dataclass(frozen=True)
class Finding:
    """A single structured observation produced by an evaluator."""

    code: str
    message: str
    severity: Severity = Severity.INFO
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvaluationOutcome:
    """The full result of running one evaluator on one trace."""

    evaluator: str
    version: str
    category: EvaluatorCategory
    verdict: Verdict
    score: float  # 0.0 - 1.0
    confidence: float  # 0.0 - 1.0
    summary: str
    findings: list[Finding] = field(default_factory=list)
    duration_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def weighted_score(self) -> float:
        """Score discounted by confidence — used in aggregation."""
        return self.score * self.confidence

    def highest_severity(self) -> Severity:
        if not self.findings:
            return Severity.INFO
        order = list(Severity)
        return max(self.findings, key=lambda f: order.index(f.severity)).severity


@dataclass(frozen=True)
class EvaluatorConfigField:
    """Declares one tunable config field so the UI can render it."""

    name: str
    type: str  # "float" | "int" | "bool" | "str" | "enum"
    default: Any
    description: str
    minimum: float | None = None
    maximum: float | None = None
    choices: tuple[str, ...] | None = None


@dataclass(frozen=True)
class EvaluatorSpec:
    """Self-description of an evaluator for discovery, config, and versioning."""

    name: str
    version: str
    category: EvaluatorCategory
    title: str
    description: str
    default_weight: float = 1.0
    blocking_by_default: bool = True
    config_fields: tuple[EvaluatorConfigField, ...] = ()
    requires_ground_truth: bool = False
    requires_llm_judge: bool = False


@dataclass
class EvalContext:
    """Everything an evaluator needs to do its job."""

    trace: Trace
    ground_truth: dict[str, Any] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)
    baseline: dict[str, Any] = field(default_factory=dict)

    def cfg(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)


class Evaluator(abc.ABC):
    """Base class for all evaluators."""

    spec: EvaluatorSpec

    @abc.abstractmethod
    def _run(self, ctx: EvalContext) -> EvaluationOutcome:
        """Concrete evaluation logic. Must not raise for normal failures —
        return a FAIL/WARN verdict instead. Raising is reserved for true
        evaluator bugs, which the harness converts into an ERROR verdict."""

    def evaluate(self, ctx: EvalContext) -> EvaluationOutcome:
        """Run with timing and error isolation."""
        start = time.perf_counter()
        try:
            outcome = self._run(ctx)
        except Exception as exc:  # evaluator bug → ERROR, never crash the run
            outcome = EvaluationOutcome(
                evaluator=self.spec.name,
                version=self.spec.version,
                category=self.spec.category,
                verdict=Verdict.ERROR,
                score=0.0,
                confidence=1.0,
                summary=f"Evaluator raised: {type(exc).__name__}: {exc}",
                findings=[
                    Finding(
                        code="evaluator_exception",
                        message=str(exc),
                        severity=Severity.HIGH,
                    )
                ],
            )
        outcome.duration_ms = (time.perf_counter() - start) * 1000.0
        return outcome

    # Convenience builders for subclasses ---------------------------------

    def _outcome(
        self,
        verdict: Verdict,
        score: float,
        summary: str,
        *,
        confidence: float = 1.0,
        findings: Iterable[Finding] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> EvaluationOutcome:
        return EvaluationOutcome(
            evaluator=self.spec.name,
            version=self.spec.version,
            category=self.spec.category,
            verdict=verdict,
            score=score,
            confidence=confidence,
            summary=summary,
            findings=list(findings or []),
            metadata=metadata or {},
        )


class EvaluatorRegistry:
    """Holds available evaluators keyed by name; supports discovery."""

    def __init__(self) -> None:
        self._evaluators: dict[str, Evaluator] = {}

    def register(self, evaluator: Evaluator) -> Evaluator:
        name = evaluator.spec.name
        if name in self._evaluators:
            raise ValueError(f"Evaluator already registered: {name}")
        self._evaluators[name] = evaluator
        return evaluator

    def get(self, name: str) -> Evaluator:
        if name not in self._evaluators:
            raise KeyError(f"Unknown evaluator: {name}")
        return self._evaluators[name]

    def all(self) -> list[Evaluator]:
        return list(self._evaluators.values())

    def specs(self) -> list[EvaluatorSpec]:
        return [e.spec for e in self._evaluators.values()]

    def names(self) -> list[str]:
        return list(self._evaluators.keys())

    def __len__(self) -> int:
        return len(self._evaluators)

    def __contains__(self, name: object) -> bool:
        return name in self._evaluators

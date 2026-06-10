"""Domain event definitions.

Events are immutable records of something that happened in the domain. They
carry enough context for any handler to react without reaching back into the
service that emitted them.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _now() -> datetime:
    return datetime.now(timezone.utc)


class EventType(str, enum.Enum):
    TRACE_EVALUATED = "trace_evaluated"
    BLOCKING_FAILURE = "blocking_failure"
    GATE_DECIDED = "gate_decided"
    REGRESSION_DETECTED = "regression_detected"


@dataclass(frozen=True)
class DomainEvent:
    type: EventType
    tenant_id: str
    payload: dict[str, Any] = field(default_factory=dict)
    occurred_at: datetime = field(default_factory=_now)


@dataclass(frozen=True)
class TraceEvaluated(DomainEvent):
    @classmethod
    def make(cls, tenant_id: str, trace_id: str, intent: str, aggregate: float, passed: bool) -> "DomainEvent":
        return DomainEvent(
            type=EventType.TRACE_EVALUATED,
            tenant_id=tenant_id,
            payload={"trace_id": trace_id, "intent": intent, "aggregate": aggregate, "passed": passed},
        )


def blocking_failure(tenant_id: str, trace_id: str, evaluators: list[str], detail: str) -> DomainEvent:
    return DomainEvent(
        type=EventType.BLOCKING_FAILURE,
        tenant_id=tenant_id,
        payload={"trace_id": trace_id, "evaluators": evaluators, "detail": detail},
    )


def gate_decided(tenant_id: str, candidate: str, passed: bool, aggregate: float) -> DomainEvent:
    return DomainEvent(
        type=EventType.GATE_DECIDED,
        tenant_id=tenant_id,
        payload={"candidate": candidate, "passed": passed, "aggregate": aggregate},
    )


def regression_detected(tenant_id: str, candidate: str, regressions: list[str]) -> DomainEvent:
    return DomainEvent(
        type=EventType.REGRESSION_DETECTED,
        tenant_id=tenant_id,
        payload={"candidate": candidate, "regressions": regressions},
    )

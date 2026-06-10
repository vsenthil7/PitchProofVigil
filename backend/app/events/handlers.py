"""Event handlers — side-effects subscribed to the bus.

Handlers are intentionally small and single-purpose. They are wired onto a bus
by ``register_default_handlers``. Persistence-backed handlers (audit) are
created per-request with a session; the metrics handler is process-global.
"""
from __future__ import annotations

from app.events.types import DomainEvent, EventType
from app.observability.metrics import Metrics
from app.repositories.audit import AuditRepository


class MetricsHandler:
    """Translates domain events into Prometheus metric movements."""

    def __init__(self, metrics: Metrics) -> None:
        self.metrics = metrics

    def __call__(self, event: DomainEvent) -> None:
        if event.type == EventType.GATE_DECIDED:
            self.metrics.observe_gate(bool(event.payload.get("passed")))


class AuditHandler:
    """Persists significant events into the tenant audit log."""

    ACTIONS = {
        EventType.BLOCKING_FAILURE: "eval.blocking_failure",
        EventType.GATE_DECIDED: "gate.decided",
        EventType.REGRESSION_DETECTED: "gate.regression",
    }

    def __init__(self, audit_repo: AuditRepository) -> None:
        self.audit_repo = audit_repo

    async def __call__(self, event: DomainEvent) -> None:
        action = self.ACTIONS.get(event.type)
        if action is None:
            return
        from app.crypto.redaction import redact

        await self.audit_repo.record(
            action=action,
            target=str(event.payload.get("candidate") or event.payload.get("trace_id") or ""),
            detail=redact(event.payload),
        )


class WebhookHandler:
    """Fans a domain event out to every matching webhook subscription.

    The event type maps to the subscription's ``event_type`` string. Delivery
    is delegated to the WebhookDeliveryService (signed, retried, status-saved).
    """

    def __init__(self, delivery_service) -> None:
        self.delivery = delivery_service

    async def __call__(self, event) -> None:
        await self.delivery.deliver_to_event(
            event.type.value,
            {
                "type": event.type.value,
                "tenant_id": event.tenant_id,
                "payload": event.payload,
                "occurred_at": event.occurred_at.isoformat(),
            },
        )

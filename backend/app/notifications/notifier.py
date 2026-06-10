"""Unified notification fan-out.

Wires a per-request EventBus with the standard set of handlers: audit
persistence, metrics, and live webhook delivery. Centralizing this assembly
keeps routers thin and guarantees every entry point emits the same side
effects.
"""
from __future__ import annotations

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.events.bus import EventBus
from app.events.handlers import AuditHandler, MetricsHandler, WebhookHandler
from app.observability.metrics import Metrics
from app.repositories.audit import AuditRepository, WebhookRepository
from app.webhooks.delivery import WebhookDeliveryService


def build_event_bus(
    session: AsyncSession,
    tenant_id: str,
    metrics: Metrics,
    http_client: httpx.AsyncClient | None = None,
    cipher=None,
) -> EventBus:
    """Assemble an EventBus with audit, metrics, and webhook handlers."""
    bus = EventBus()
    bus.subscribe_all(AuditHandler(AuditRepository(session, tenant_id)))
    bus.subscribe_all(MetricsHandler(metrics))
    delivery = WebhookDeliveryService(
        WebhookRepository(session, tenant_id, cipher=cipher), client=http_client
    )
    bus.subscribe_all(WebhookHandler(delivery))
    return bus

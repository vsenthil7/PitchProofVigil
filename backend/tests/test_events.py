"""Tests for the domain event bus, types, and handlers."""
from __future__ import annotations

import pytest

from app.events.bus import EventBus
from app.events.handlers import AuditHandler, MetricsHandler
from app.events.types import (
    DomainEvent,
    EventType,
    TraceEvaluated,
    blocking_failure,
    gate_decided,
    regression_detected,
)
from app.observability.metrics import Metrics
from app.repositories.audit import AuditRepository


# ---- Event types ----

def test_event_factories():
    e1 = TraceEvaluated.make("t", "tr1", "kickoff_time", 0.9, True)
    assert e1.type == EventType.TRACE_EVALUATED
    assert e1.payload["trace_id"] == "tr1"
    e2 = blocking_failure("t", "tr1", ["factual_accuracy"], "mismatch")
    assert e2.type == EventType.BLOCKING_FAILURE
    e3 = gate_decided("t", "v2", False, 0.4)
    assert e3.type == EventType.GATE_DECIDED
    e4 = regression_detected("t", "v2", ["correctness: -0.5"])
    assert e4.type == EventType.REGRESSION_DETECTED
    assert e4.payload["regressions"] == ["correctness: -0.5"]


# ---- Bus ----

async def test_bus_dispatches_to_matching_handler():
    bus = EventBus()
    seen = []
    bus.subscribe(EventType.GATE_DECIDED, lambda e: seen.append(e.payload["candidate"]))
    errs = await bus.publish(gate_decided("t", "v1", True, 0.9))
    assert errs == []
    assert seen == ["v1"]


async def test_bus_global_handler():
    bus = EventBus()
    seen = []
    bus.subscribe_all(lambda e: seen.append(e.type))
    await bus.publish(gate_decided("t", "v1", True, 0.9))
    await bus.publish(blocking_failure("t", "tr", [], "x"))
    assert len(seen) == 2


async def test_bus_async_handler():
    bus = EventBus()
    seen = []

    async def handler(e):
        seen.append(e.type)

    bus.subscribe(EventType.GATE_DECIDED, handler)
    await bus.publish(gate_decided("t", "v1", True, 0.9))
    assert seen == [EventType.GATE_DECIDED]


async def test_bus_isolates_handler_errors():
    bus = EventBus()
    ok = []

    def boom(e):
        raise RuntimeError("handler bug")

    bus.subscribe(EventType.GATE_DECIDED, boom)
    bus.subscribe(EventType.GATE_DECIDED, lambda e: ok.append(1))
    errs = await bus.publish(gate_decided("t", "v1", True, 0.9))
    assert len(errs) == 1
    assert ok == [1]  # second handler still ran


def test_bus_handler_count():
    bus = EventBus()
    bus.subscribe(EventType.GATE_DECIDED, lambda e: None)
    bus.subscribe_all(lambda e: None)
    assert bus.handler_count(EventType.GATE_DECIDED) == 2
    assert bus.handler_count(EventType.TRACE_EVALUATED) == 1  # global only


# ---- Handlers ----

async def test_metrics_handler():
    m = Metrics()
    h = MetricsHandler(m)
    h(gate_decided("t", "v1", True, 0.9))
    data, _ = m.render()
    assert b"ppv_gate_decisions_total" in data


async def test_metrics_handler_ignores_other_events():
    m = Metrics()
    h = MetricsHandler(m)
    h(blocking_failure("t", "tr", [], "x"))  # no gate metric movement, no raise


async def test_audit_handler_persists(db, tenant_id):
    async with db.session() as s:
        handler = AuditHandler(AuditRepository(s, tenant_id))
        await handler(gate_decided(tenant_id, "v2", False, 0.4))
        await handler(blocking_failure(tenant_id, "tr1", ["x"], "detail"))
        await handler(regression_detected(tenant_id, "v2", ["correctness"]))
    async with db.session() as s:
        rows = await AuditRepository(s, tenant_id).list()
        actions = {r.action for r in rows}
        assert "gate.decided" in actions
        assert "eval.blocking_failure" in actions
        assert "gate.regression" in actions


async def test_audit_handler_ignores_unmapped(db, tenant_id):
    async with db.session() as s:
        handler = AuditHandler(AuditRepository(s, tenant_id))
        await handler(DomainEvent(type=EventType.TRACE_EVALUATED, tenant_id=tenant_id))
    async with db.session() as s:
        assert await AuditRepository(s, tenant_id).list() == []

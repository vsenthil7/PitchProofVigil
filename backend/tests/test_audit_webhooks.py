"""Tests for audit and webhook repositories."""
from __future__ import annotations

from app.repositories.audit import AuditRepository, WebhookRepository


# ---- Audit ----

async def test_audit_record_and_list(db, tenant_id):
    async with db.session() as s:
        repo = AuditRepository(s, tenant_id)
        await repo.record("policy.created", actor="o@wc.com", target="production", detail={"v": 1})
        await repo.record("gate.decided", target="v2")
    async with db.session() as s:
        repo = AuditRepository(s, tenant_id)
        rows = await repo.list()
        assert len(rows) == 2
        assert rows[0].actor in ("o@wc.com", "system")


async def test_audit_filter_by_action(db, tenant_id):
    async with db.session() as s:
        repo = AuditRepository(s, tenant_id)
        await repo.record("gate.decided", target="v1")
        await repo.record("gate.decided", target="v2")
        await repo.record("policy.created", target="p")
    async with db.session() as s:
        repo = AuditRepository(s, tenant_id)
        gate_rows = await repo.filter_by_action("gate.decided")
        assert len(gate_rows) == 2


async def test_audit_tenant_isolation(db, tenant_id):
    async with db.session() as s:
        await AuditRepository(s, tenant_id).record("x")
    async with db.session() as s:
        assert await AuditRepository(s, "other").list() == []


# ---- Webhooks ----

async def test_webhook_create_and_for_event(db, tenant_id):
    async with db.session() as s:
        repo = WebhookRepository(s, tenant_id)
        await repo.create("https://hook/a", "gate_decided", "sec1")
        await repo.create("https://hook/b", "blocking_failure")
    async with db.session() as s:
        repo = WebhookRepository(s, tenant_id)
        gate_hooks = await repo.for_event("gate_decided")
        assert len(gate_hooks) == 1
        assert gate_hooks[0].url == "https://hook/a"
        assert len(await repo.list()) == 2


async def test_webhook_deactivate(db, tenant_id):
    async with db.session() as s:
        repo = WebhookRepository(s, tenant_id)
        w = await repo.create("https://hook/a", "gate_decided")
        wid = w.id
    async with db.session() as s:
        repo = WebhookRepository(s, tenant_id)
        assert await repo.deactivate(wid) is True
        assert await repo.for_event("gate_decided") == []
        assert await repo.deactivate("missing") is False


async def test_webhook_deactivate_wrong_tenant(db, tenant_id):
    async with db.session() as s:
        w = await WebhookRepository(s, tenant_id).create("https://hook/a", "gate_decided")
        wid = w.id
    async with db.session() as s:
        assert await WebhookRepository(s, "other").deactivate(wid) is False


async def test_webhook_mark_delivery(db, tenant_id):
    async with db.session() as s:
        repo = WebhookRepository(s, tenant_id)
        w = await repo.create("https://hook/a", "gate_decided")
        await repo.mark_delivery(w, 200)
        assert w.last_status == 200
        assert w.last_delivery_at is not None

"""Tests for webhook signing, delivery, and the event handler."""
from __future__ import annotations

import json

import httpx
import pytest

from app.events.handlers import WebhookHandler
from app.events.types import gate_decided
from app.notifications import build_event_bus
from app.observability.metrics import Metrics
from app.repositories.audit import WebhookRepository
from app.webhooks.delivery import WebhookDeliveryService
from app.webhooks.signing import sign_payload, verify_signature


# ---- Signing ----

def test_sign_and_verify_roundtrip():
    body = b'{"a":1}'
    header = sign_payload("secret", body, timestamp=1000)
    assert header.startswith("t=1000,v1=")
    # Verify with a fresh tolerance window centered on now would fail (old ts);
    # use a large tolerance to validate the digest math.
    assert verify_signature("secret", body, header, tolerance_s=10**12)


def test_verify_rejects_wrong_secret():
    body = b'{"a":1}'
    header = sign_payload("secret", body, timestamp=1000)
    assert not verify_signature("other", body, header, tolerance_s=10**12)


def test_verify_rejects_tampered_body():
    header = sign_payload("secret", b'{"a":1}', timestamp=1000)
    assert not verify_signature("secret", b'{"a":2}', header, tolerance_s=10**12)


def test_verify_rejects_stale_timestamp():
    header = sign_payload("secret", b"x", timestamp=1)  # ancient
    assert not verify_signature("secret", b"x", header, tolerance_s=10)


def test_verify_rejects_malformed_header():
    assert not verify_signature("s", b"x", "garbage")
    assert not verify_signature("s", b"x", "t=notanumber,v1=abc")


# ---- Delivery ----

async def test_delivery_success(db, tenant_id):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["sig"] = request.headers.get("X-PPV-Signature")
        captured["event"] = request.headers.get("X-PPV-Event")
        captured["body"] = request.content
        return httpx.Response(200)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    async with db.session() as s:
        repo = WebhookRepository(s, tenant_id)
        sub = await repo.create("https://hook/x", "gate_decided", "sec")
        svc = WebhookDeliveryService(repo, client=client)
        result = await svc.deliver(sub, {"hello": "world"})
        assert result.delivered is True
        assert result.status == 200
        assert captured["event"] == "gate_decided"
        assert captured["sig"].startswith("t=")
        # Body is signed and verifiable.
        assert verify_signature("sec", captured["body"], captured["sig"], tolerance_s=10**12)
    await client.aclose()


async def test_delivery_retries_on_5xx_then_fails(db, tenant_id):
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    async with db.session() as s:
        repo = WebhookRepository(s, tenant_id)
        sub = await repo.create("https://hook/x", "gate_decided")
        from app.orchestration.resilience import RetryPolicy

        svc = WebhookDeliveryService(
            repo, client=client, retry=RetryPolicy(max_attempts=3, sleep=lambda s: None)
        )
        result = await svc.deliver(sub, {"x": 1})
        assert result.delivered is False
        assert result.attempts == 3
        assert calls["n"] == 3


async def test_delivery_4xx_no_retry(db, tenant_id):
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    async with db.session() as s:
        repo = WebhookRepository(s, tenant_id)
        sub = await repo.create("https://hook/x", "gate_decided")
        svc = WebhookDeliveryService(repo, client=client)
        result = await svc.deliver(sub, {"x": 1})
        assert result.delivered is False
        assert result.status == 404
        assert calls["n"] == 1  # 4xx is terminal, no retry
    await client.aclose()


async def test_deliver_to_event_fans_out(db, tenant_id):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    async with db.session() as s:
        repo = WebhookRepository(s, tenant_id)
        await repo.create("https://a/hook", "gate_decided")
        await repo.create("https://b/hook", "gate_decided")
        await repo.create("https://c/hook", "blocking_failure")  # different event
        svc = WebhookDeliveryService(repo, client=client)
        results = await svc.deliver_to_event("gate_decided", {"x": 1})
        assert len(results) == 2  # only the two gate_decided subs
        assert len(seen) == 2
    await client.aclose()


# ---- Handler + notifier ----

async def test_webhook_handler_dispatches(db, tenant_id):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("X-PPV-Event"))
        return httpx.Response(200)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    async with db.session() as s:
        repo = WebhookRepository(s, tenant_id)
        await repo.create("https://hook/x", "gate_decided")
        svc = WebhookDeliveryService(repo, client=client)
        wh = WebhookHandler(svc)
        await wh(gate_decided(tenant_id, "v1", True, 0.9))
        assert seen == ["gate_decided"]
    await client.aclose()


async def test_build_event_bus_has_all_handlers(db, tenant_id):
    async with db.session() as s:
        bus = build_event_bus(s, tenant_id, Metrics())
        # audit + metrics + webhook = 3 global handlers
        from app.events.types import EventType

        assert bus.handler_count(EventType.GATE_DECIDED) == 3


async def test_delivery_auto_creates_and_closes_client(db, tenant_id, monkeypatch):
    """No injected client → service creates one and closes it (cleanup path)."""
    closed = {"v": False}

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def post(self, url, content, headers):
            return httpx.Response(200)

        async def aclose(self):
            closed["v"] = True

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    async with db.session() as s:
        repo = WebhookRepository(s, tenant_id)
        sub = await repo.create("https://hook/x", "gate_decided")
        svc = WebhookDeliveryService(repo)  # no client injected
        result = await svc.deliver(sub, {"x": 1})
        assert result.delivered is True
    assert closed["v"] is True

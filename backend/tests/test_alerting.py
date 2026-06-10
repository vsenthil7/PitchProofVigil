"""Tests for the alerting service and channels."""
from __future__ import annotations

import httpx
import pytest

from app.alerting.service import AlertingService, LogChannel, WebhookChannel
from app.db.models import AlertChannel
from app.repositories.registry import AlertRepository


async def test_log_channel_delivers(db, tenant_id):
    async with db.session() as s:
        svc = AlertingService(AlertRepository(s, tenant_id), LogChannel())
        alert = await svc.raise_alert("high", "Title", "Body", {"k": "v"})
        assert alert.delivered is True
        assert alert.channel == AlertChannel.LOG
    async with db.session() as s:
        svc = AlertingService(AlertRepository(s, tenant_id))
        alerts = await svc.list()
        assert len(alerts) == 1


async def test_webhook_channel_success(db, tenant_id):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    channel = WebhookChannel("https://hook.example/alert", client=client)
    async with db.session() as s:
        svc = AlertingService(AlertRepository(s, tenant_id), channel)
        alert = await svc.raise_alert("high", "T", "B")
        assert alert.delivered is True
        assert alert.channel == AlertChannel.WEBHOOK
    await client.aclose()


async def test_webhook_channel_non_2xx(db, tenant_id):
    transport = httpx.MockTransport(lambda req: httpx.Response(500))
    client = httpx.AsyncClient(transport=transport)
    channel = WebhookChannel("https://hook.example/alert", client=client)
    async with db.session() as s:
        svc = AlertingService(AlertRepository(s, tenant_id), channel)
        alert = await svc.raise_alert("high", "T", "B")
        assert alert.delivered is False
    await client.aclose()


async def test_webhook_default_channel_attr():
    channel = WebhookChannel("https://x")
    assert channel.channel == AlertChannel.WEBHOOK


async def test_webhook_auto_creates_and_closes_client(db, tenant_id, monkeypatch):
    """When no client is injected, the channel creates one and closes it.

    Exercises the `self._client is None` cleanup branch.
    """
    closed = {"value": False}

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def post(self, url, json):
            return httpx.Response(200, json={"ok": True})

        async def aclose(self):
            closed["value"] = True

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    channel = WebhookChannel("https://hook.example/alert")  # no client injected
    async with db.session() as s:
        svc = AlertingService(AlertRepository(s, tenant_id), channel)
        alert = await svc.raise_alert("low", "T", "B")
        assert alert.delivered is True
    assert closed["value"] is True

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


# ---- P5.S1: PagerDuty + Slack channels ----

def _p5_alert(channel):
    from datetime import datetime, timezone

    from app.db.models import AlertRow
    return AlertRow(
        id="test-alert-id",
        tenant_id="tenant-1",
        severity="high",
        title="Gate blocked",
        body="Candidate v1.3 blocked by llm_judge",
        channel=channel,
        context={"candidate": "v1.3", "score": 0.42},
        created_at=datetime(2026, 6, 3, tzinfo=timezone.utc),
    )


async def test_pagerduty_channel_posts_correct_payload():
    from unittest.mock import AsyncMock, MagicMock

    from app.alerting.service import PagerDutyChannel
    from app.db.models import AlertChannel

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 202
    mock_client.post = AsyncMock(return_value=mock_resp)

    channel = PagerDutyChannel(routing_key="test-routing-key", client=mock_client)
    result = await channel.send(_p5_alert(AlertChannel.PAGERDUTY))
    assert result is True
    payload = mock_client.post.call_args.kwargs["json"]
    assert payload["routing_key"] == "test-routing-key"
    assert payload["event_action"] == "trigger"
    assert payload["dedup_key"] == "test-alert-id"
    assert payload["payload"]["severity"] == "error"  # high -> error


async def test_pagerduty_channel_returns_false_on_http_error():
    from unittest.mock import AsyncMock, MagicMock

    from app.alerting.service import PagerDutyChannel
    from app.db.models import AlertChannel

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_client.post = AsyncMock(return_value=mock_resp)
    channel = PagerDutyChannel(routing_key="key", client=mock_client)
    assert await channel.send(_p5_alert(AlertChannel.PAGERDUTY)) is False


async def test_pagerduty_channel_returns_false_on_exception():
    from unittest.mock import AsyncMock, MagicMock

    from app.alerting.service import PagerDutyChannel
    from app.db.models import AlertChannel

    mock_client = MagicMock()
    mock_client.post = AsyncMock(side_effect=ConnectionError("PD down"))
    channel = PagerDutyChannel(routing_key="key", client=mock_client)
    assert await channel.send(_p5_alert(AlertChannel.PAGERDUTY)) is False


async def test_slack_channel_posts_block_kit_payload():
    from unittest.mock import AsyncMock, MagicMock

    from app.alerting.service import SlackChannel
    from app.db.models import AlertChannel

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_client.post = AsyncMock(return_value=mock_resp)

    channel = SlackChannel(webhook_url="https://hooks.slack.com/test", client=mock_client)
    result = await channel.send(_p5_alert(AlertChannel.SLACK))
    assert result is True
    payload = mock_client.post.call_args.kwargs["json"]
    assert "attachments" in payload and len(payload["attachments"]) == 1
    blocks = payload["attachments"][0]["blocks"]
    assert any(b.get("type") == "header" for b in blocks)
    assert payload["attachments"][0]["color"] == "#FF6600"  # high


async def test_slack_channel_returns_false_on_exception():
    from unittest.mock import AsyncMock, MagicMock

    from app.alerting.service import SlackChannel
    from app.db.models import AlertChannel

    mock_client = MagicMock()
    mock_client.post = AsyncMock(side_effect=ConnectionError("Slack down"))
    channel = SlackChannel(webhook_url="https://hooks.slack.com/test", client=mock_client)
    assert await channel.send(_p5_alert(AlertChannel.SLACK)) is False


async def test_pagerduty_channel_creates_own_client_and_closes(monkeypatch):
    """No injected client -> channel builds its own httpx client and closes it."""
    from unittest.mock import AsyncMock, MagicMock

    import app.alerting.service as svc
    from app.db.models import AlertChannel

    created = MagicMock()
    resp = MagicMock()
    resp.status_code = 202
    created.post = AsyncMock(return_value=resp)
    created.aclose = AsyncMock()
    monkeypatch.setattr(svc.httpx, "AsyncClient", lambda *a, **k: created)

    channel = svc.PagerDutyChannel(routing_key="k")  # no client injected
    assert await channel.send(_p5_alert(AlertChannel.PAGERDUTY)) is True
    created.aclose.assert_awaited_once()


async def test_slack_channel_creates_own_client_and_closes(monkeypatch):
    from unittest.mock import AsyncMock, MagicMock

    import app.alerting.service as svc
    from app.db.models import AlertChannel

    created = MagicMock()
    resp = MagicMock()
    resp.status_code = 200
    created.post = AsyncMock(return_value=resp)
    created.aclose = AsyncMock()
    monkeypatch.setattr(svc.httpx, "AsyncClient", lambda *a, **k: created)

    channel = svc.SlackChannel(webhook_url="https://hooks.slack.com/x")  # no client
    assert await channel.send(_p5_alert(AlertChannel.SLACK)) is True
    created.aclose.assert_awaited_once()

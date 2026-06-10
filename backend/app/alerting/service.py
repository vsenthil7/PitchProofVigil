"""Alerting service.

Persists alerts and dispatches them through a channel. The LogChannel always
works (writes a structured log); WebhookChannel posts JSON to a URL. Dispatch
failures never propagate — an alert that can't be delivered is still recorded
as undelivered so it is visible in the dashboard.
"""
from __future__ import annotations

import abc

import httpx

from app.db.models import AlertChannel, AlertRow
from app.observability.logging import get_logger
from app.repositories.registry import AlertRepository

_log = get_logger("alerting")

# Map internal severities onto PagerDuty Events API v2 severities.
_SEVERITY_MAP = {
    "critical": "critical",
    "high": "error",
    "medium": "warning",
    "low": "info",
    "info": "info",
}

# Slack attachment colours per severity.
_SLACK_COLOURS = {
    "critical": "#FF0000",
    "high": "#FF6600",
    "medium": "#FFCC00",
    "low": "#36A64F",
    "info": "#439FE0",
}


class Channel(abc.ABC):
    channel: AlertChannel

    @abc.abstractmethod
    async def send(self, alert: AlertRow) -> bool:
        """Deliver the alert. Return True on success."""


class LogChannel(Channel):
    channel = AlertChannel.LOG

    async def send(self, alert: AlertRow) -> bool:
        _log.warning(
            "alert",
            severity=alert.severity,
            title=alert.title,
            body=alert.body,
            tenant_id=alert.tenant_id,
        )
        return True


class WebhookChannel(Channel):
    channel = AlertChannel.WEBHOOK

    def __init__(self, url: str, client: httpx.AsyncClient | None = None) -> None:
        self.url = url
        self._client = client

    async def send(self, alert: AlertRow) -> bool:
        payload = {
            "severity": alert.severity,
            "title": alert.title,
            "body": alert.body,
            "context": alert.context,
        }
        try:
            client = self._client or httpx.AsyncClient(timeout=5.0)
            try:
                resp = await client.post(self.url, json=payload)
                return 200 <= resp.status_code < 300
            finally:
                if self._client is None:
                    await client.aclose()
        except Exception:  # pragma: no cover - network failure path
            return False


class PagerDutyChannel(Channel):
    """Posts a PagerDuty Events API v2 trigger event."""

    channel = AlertChannel.PAGERDUTY
    _PD_URL = "https://events.pagerduty.com/v2/enqueue"

    def __init__(
        self, routing_key: str, client: httpx.AsyncClient | None = None
    ) -> None:
        self.routing_key = routing_key
        self._client = client

    async def send(self, alert: AlertRow) -> bool:
        payload = {
            "routing_key": self.routing_key,
            "event_action": "trigger",
            "payload": {
                "summary": f"[{alert.severity.upper()}] {alert.title}",
                "severity": _SEVERITY_MAP.get(alert.severity, "warning"),
                "source": "pitchproof-vigil",
                "custom_details": alert.context,
                "timestamp": alert.created_at.isoformat(),
            },
            "dedup_key": alert.id,
        }
        try:
            client = self._client or httpx.AsyncClient(timeout=5.0)
            try:
                resp = await client.post(self._PD_URL, json=payload)
                return 200 <= resp.status_code < 300
            finally:
                if self._client is None:
                    await client.aclose()
        except Exception:
            return False


class SlackChannel(Channel):
    """Posts a Slack Block Kit message to an incoming webhook URL."""

    channel = AlertChannel.SLACK

    def __init__(
        self, webhook_url: str, client: httpx.AsyncClient | None = None
    ) -> None:
        self.webhook_url = webhook_url
        self._client = client

    async def send(self, alert: AlertRow) -> bool:
        colour = _SLACK_COLOURS.get(alert.severity, "#cccccc")
        payload = {
            "attachments": [
                {
                    "color": colour,
                    "blocks": [
                        {
                            "type": "header",
                            "text": {
                                "type": "plain_text",
                                "text": f":bell: [{alert.severity.upper()}] {alert.title}",
                            },
                        },
                        {
                            "type": "section",
                            "text": {"type": "mrkdwn", "text": alert.body},
                        },
                        {
                            "type": "context",
                            "elements": [
                                {
                                    "type": "mrkdwn",
                                    "text": (
                                        f"*Tenant:* {alert.tenant_id} | "
                                        f"*ID:* {alert.id}"
                                    ),
                                }
                            ],
                        },
                    ],
                }
            ]
        }
        try:
            client = self._client or httpx.AsyncClient(timeout=5.0)
            try:
                resp = await client.post(self.webhook_url, json=payload)
                return 200 <= resp.status_code < 300
            finally:
                if self._client is None:
                    await client.aclose()
        except Exception:
            return False


class AlertingService:
    """Create, persist, and dispatch alerts."""

    def __init__(self, repo: AlertRepository, channel: Channel | None = None) -> None:
        self.repo = repo
        self.channel = channel or LogChannel()

    async def raise_alert(
        self,
        severity: str,
        title: str,
        body: str,
        context: dict | None = None,
    ) -> AlertRow:
        alert = AlertRow(
            tenant_id=self.repo.tenant_id,
            severity=severity,
            title=title,
            body=body,
            channel=self.channel.channel,
            context=context or {},
        )
        await self.repo.add(alert)
        delivered = await self.channel.send(alert)
        alert.delivered = delivered
        await self.repo.session.flush()
        return alert

    async def list(self, limit: int = 50) -> list[AlertRow]:
        return await self.repo.list(limit=limit)

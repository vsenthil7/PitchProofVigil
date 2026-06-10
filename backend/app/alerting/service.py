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

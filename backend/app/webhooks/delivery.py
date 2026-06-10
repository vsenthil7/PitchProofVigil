"""Webhook delivery service.

Posts a signed JSON payload to a subscription's URL with bounded retry, then
persists the delivery status back onto the subscription. Network/transport
failures are swallowed (recorded as a failed status) so a flaky receiver never
breaks the emitting workflow.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import httpx

from app.db.models import WebhookSubscriptionRow
from app.observability.logging import get_logger
from app.orchestration.resilience import RetryPolicy
from app.repositories.audit import WebhookRepository
from app.webhooks.signing import sign_payload

_log = get_logger("webhook.delivery")


@dataclass
class DeliveryResult:
    subscription_id: str
    delivered: bool
    status: int | None
    attempts: int


class WebhookDeliveryService:
    """Signs, posts (with retry), and records webhook deliveries."""

    def __init__(
        self,
        repo: WebhookRepository,
        client: httpx.AsyncClient | None = None,
        retry: RetryPolicy | None = None,
        timeout_s: float = 5.0,
    ) -> None:
        self.repo = repo
        self._client = client
        self.timeout_s = timeout_s
        # 3 attempts, no real sleep in tests via injected sleep.
        self.retry = retry or RetryPolicy(
            max_attempts=3, base_delay_s=0.1, retryable=(httpx.HTTPError,)
        )

    async def _post_once(self, sub: WebhookSubscriptionRow, body: bytes, signature: str) -> int:
        client = self._client or httpx.AsyncClient(timeout=self.timeout_s)
        try:
            resp = await client.post(
                sub.url,
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-PPV-Signature": signature,
                    "X-PPV-Event": sub.event_type,
                },
            )
            if resp.status_code >= 500:
                raise httpx.HTTPError(f"server error {resp.status_code}")
            return resp.status_code
        finally:
            if self._client is None:
                await client.aclose()

    async def deliver(self, sub: WebhookSubscriptionRow, payload: dict) -> DeliveryResult:
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        signature = sign_payload(sub.secret or "", body)

        # Async retry loop (RetryPolicy is sync-only, so we mirror its policy).
        status: int | None = None
        last_exc: Exception | None = None
        attempts = 0
        for attempt in range(1, self.retry.max_attempts + 1):
            attempts = attempt
            try:
                status = await self._post_once(sub, body, signature)
                last_exc = None
                break
            except httpx.HTTPError as exc:
                last_exc = exc

        delivered = status is not None and 200 <= status < 300
        await self.repo.mark_delivery(sub, status if status is not None else 0)
        if not delivered:
            _log.warning(
                "webhook_delivery_failed",
                subscription_id=sub.id,
                status=status,
                error=str(last_exc) if last_exc else None,
            )
        return DeliveryResult(
            subscription_id=sub.id, delivered=delivered, status=status, attempts=attempts
        )

    async def deliver_to_event(self, event_type: str, payload: dict) -> list[DeliveryResult]:
        """Deliver a payload to every active subscription for an event type."""
        subs = await self.repo.for_event(event_type)
        results = []
        for sub in subs:
            results.append(await self.deliver(sub, payload))
        return results

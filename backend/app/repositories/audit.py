"""Audit log and webhook-subscription repositories (tenant-scoped)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLogRow, WebhookSubscriptionRow


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AuditRepository:
    def __init__(self, session: AsyncSession, tenant_id: str) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def record(
        self, action: str, actor: str = "system", target: str = "", detail: dict | None = None
    ) -> AuditLogRow:
        row = AuditLogRow(
            tenant_id=self.tenant_id,
            actor=actor,
            action=action,
            target=target,
            detail=detail or {},
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def list(self, limit: int = 100) -> list[AuditLogRow]:
        stmt = (
            select(AuditLogRow)
            .where(AuditLogRow.tenant_id == self.tenant_id)
            .order_by(desc(AuditLogRow.created_at))
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def filter_by_action(self, action: str, limit: int = 100) -> list[AuditLogRow]:
        stmt = (
            select(AuditLogRow)
            .where(
                AuditLogRow.tenant_id == self.tenant_id,
                AuditLogRow.action == action,
            )
            .order_by(desc(AuditLogRow.created_at))
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())


class WebhookRepository:
    def __init__(self, session: AsyncSession, tenant_id: str) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def create(self, url: str, event_type: str, secret: str = "") -> WebhookSubscriptionRow:
        row = WebhookSubscriptionRow(
            tenant_id=self.tenant_id, url=url, event_type=event_type, secret=secret
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def for_event(self, event_type: str) -> list[WebhookSubscriptionRow]:
        stmt = select(WebhookSubscriptionRow).where(
            WebhookSubscriptionRow.tenant_id == self.tenant_id,
            WebhookSubscriptionRow.event_type == event_type,
            WebhookSubscriptionRow.active == True,  # noqa: E712
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def list(self) -> list[WebhookSubscriptionRow]:
        stmt = select(WebhookSubscriptionRow).where(
            WebhookSubscriptionRow.tenant_id == self.tenant_id
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def deactivate(self, webhook_id: str) -> bool:
        row = await self.session.get(WebhookSubscriptionRow, webhook_id)
        if row is None or row.tenant_id != self.tenant_id:
            return False
        row.active = False
        self.session.add(row)
        await self.session.flush()
        return True

    async def mark_delivery(self, row: WebhookSubscriptionRow, status: int) -> None:
        row.last_delivery_at = _now()
        row.last_status = status
        self.session.add(row)
        await self.session.flush()

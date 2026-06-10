"""Audit log and webhook-subscription repositories (tenant-scoped)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import desc, func, select
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

    async def list(self, limit: int = 100, offset: int = 0) -> list[AuditLogRow]:
        stmt = (
            select(AuditLogRow)
            .where(AuditLogRow.tenant_id == self.tenant_id)
            .order_by(desc(AuditLogRow.created_at))
            .limit(limit)
            .offset(offset)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def count(self) -> int:
        stmt = (
            select(func.count())
            .select_from(AuditLogRow)
            .where(AuditLogRow.tenant_id == self.tenant_id)
        )
        return int((await self.session.execute(stmt)).scalar() or 0)

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
    def __init__(self, session: AsyncSession, tenant_id: str, cipher=None) -> None:
        self.session = session
        self.tenant_id = tenant_id
        # Optional FieldCipher: when present, secrets are encrypted at rest and
        # transparently decrypted on read. When absent, secrets pass through
        # (keeps unit tests that don't care about crypto simple).
        self.cipher = cipher

    def _decrypt_secret(self, row: WebhookSubscriptionRow) -> WebhookSubscriptionRow:
        if self.cipher is not None and row is not None:
            row.secret = self.cipher.decrypt(row.secret or "")
        return row

    async def create(self, url: str, event_type: str, secret: str = "") -> WebhookSubscriptionRow:
        stored_secret = self.cipher.encrypt(secret) if self.cipher is not None else secret
        row = WebhookSubscriptionRow(
            tenant_id=self.tenant_id, url=url, event_type=event_type, secret=stored_secret
        )
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        # Expunge so returning plaintext to the caller doesn't overwrite the
        # persisted ciphertext via the identity map.
        self.session.expunge(row)
        row.secret = secret
        return row

    async def for_event(self, event_type: str) -> list[WebhookSubscriptionRow]:
        stmt = select(WebhookSubscriptionRow).where(
            WebhookSubscriptionRow.tenant_id == self.tenant_id,
            WebhookSubscriptionRow.event_type == event_type,
            WebhookSubscriptionRow.active == True,  # noqa: E712
        )
        rows = list((await self.session.execute(stmt)).scalars().all())
        return [self._decrypt_secret(r) for r in rows]

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

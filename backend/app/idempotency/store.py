"""Idempotency store.

Records the outcome of a mutating request under a client-supplied key so that
a replay (same tenant + key) returns the original response instead of repeating
the side effect. Storage-backed and tenant-scoped.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import IdempotencyKeyRow, uuid_str


class IdempotencyStore:
    def __init__(self, session: AsyncSession, tenant_id: str) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def get(self, key: str) -> IdempotencyKeyRow | None:
        stmt = select(IdempotencyKeyRow).where(
            IdempotencyKeyRow.tenant_id == self.tenant_id,
            IdempotencyKeyRow.key == key,
        )
        return (await self.session.execute(stmt)).scalars().first()

    async def record(
        self, key: str, method: str, path: str, code: int, body: dict
    ) -> IdempotencyKeyRow:
        row = IdempotencyKeyRow(
            id=uuid_str(),
            tenant_id=self.tenant_id,
            key=key,
            method=method,
            path=path,
            response_code=code,
            response_body=body,
        )
        self.session.add(row)
        await self.session.flush()
        return row

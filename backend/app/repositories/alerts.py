"""Alert repository."""
from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AlertRow


class AlertRepository:
    def __init__(self, session: AsyncSession, tenant_id: str) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def add(self, row: AlertRow) -> AlertRow:
        row.tenant_id = self.tenant_id
        self.session.add(row)
        await self.session.flush()
        return row

    async def list(self, limit: int = 50) -> list[AlertRow]:
        stmt = (
            select(AlertRow)
            .where(AlertRow.tenant_id == self.tenant_id)
            .order_by(desc(AlertRow.created_at))
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())

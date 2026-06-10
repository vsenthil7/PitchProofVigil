"""Governance repositories: gate policies, decisions, golden datasets."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import GateDecisionRow, GatePolicyRow, GoldenDatasetRow


def _now() -> datetime:
    return datetime.now(timezone.utc)


class GatePolicyRepository:
    def __init__(self, session: AsyncSession, tenant_id: str) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def upsert(self, row: GatePolicyRow) -> GatePolicyRow:
        row.tenant_id = self.tenant_id
        # New version if one already exists with this name.
        stmt = (
            select(func.max(GatePolicyRow.version))
            .where(
                GatePolicyRow.tenant_id == self.tenant_id,
                GatePolicyRow.name == row.name,
            )
        )
        current = (await self.session.execute(stmt)).scalar_one_or_none()
        row.version = (current or 0) + 1
        self.session.add(row)
        await self.session.flush()
        return row

    async def get_active(self, name: str) -> GatePolicyRow | None:
        stmt = (
            select(GatePolicyRow)
            .where(
                GatePolicyRow.tenant_id == self.tenant_id,
                GatePolicyRow.name == name,
                GatePolicyRow.is_active == True,  # noqa: E712
            )
            .order_by(desc(GatePolicyRow.version))
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list(self) -> list[GatePolicyRow]:
        stmt = select(GatePolicyRow).where(
            GatePolicyRow.tenant_id == self.tenant_id
        ).order_by(desc(GatePolicyRow.created_at))
        return list((await self.session.execute(stmt)).scalars().all())


class GateDecisionRepository:
    def __init__(self, session: AsyncSession, tenant_id: str) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def add(self, row: GateDecisionRow) -> GateDecisionRow:
        row.tenant_id = self.tenant_id
        self.session.add(row)
        await self.session.flush()
        return row

    async def list(self, limit: int = 50) -> list[GateDecisionRow]:
        stmt = (
            select(GateDecisionRow)
            .where(GateDecisionRow.tenant_id == self.tenant_id)
            .order_by(desc(GateDecisionRow.created_at))
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def latest_passing(self, candidate_prefix: str = "") -> GateDecisionRow | None:
        stmt = (
            select(GateDecisionRow)
            .where(
                GateDecisionRow.tenant_id == self.tenant_id,
                GateDecisionRow.passed == True,  # noqa: E712
            )
            .order_by(desc(GateDecisionRow.created_at))
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()


class GoldenDatasetRepository:
    def __init__(self, session: AsyncSession, tenant_id: str) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def create(self, row: GoldenDatasetRow) -> GoldenDatasetRow:
        row.tenant_id = self.tenant_id
        self.session.add(row)
        await self.session.flush()
        return row

    async def get(self, name: str) -> GoldenDatasetRow | None:
        stmt = select(GoldenDatasetRow).where(
            GoldenDatasetRow.tenant_id == self.tenant_id,
            GoldenDatasetRow.name == name,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def add_example(self, name: str, example: dict) -> GoldenDatasetRow | None:
        row = await self.get(name)
        if row is None:
            return None
        row.examples = [*row.examples, example]
        row.updated_at = _now()
        self.session.add(row)
        await self.session.flush()
        return row

    async def list(self) -> list[GoldenDatasetRow]:
        stmt = select(GoldenDatasetRow).where(
            GoldenDatasetRow.tenant_id == self.tenant_id
        )
        return list((await self.session.execute(stmt)).scalars().all())

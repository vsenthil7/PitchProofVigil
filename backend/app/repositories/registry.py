"""Repositories for identity, gate policies/decisions, datasets, and alerts."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AlertRow,
    APIKey,
    GateDecisionRow,
    GatePolicyRow,
    GoldenDatasetRow,
    Tenant,
    User,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TenantRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, name: str, slug: str) -> Tenant:
        tenant = Tenant(name=name, slug=slug)
        self.session.add(tenant)
        await self.session.flush()
        return tenant

    async def get(self, tenant_id: str) -> Tenant | None:
        return await self.session.get(Tenant, tenant_id)

    async def get_by_slug(self, slug: str) -> Tenant | None:
        stmt = select(Tenant).where(Tenant.slug == slug)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list(self) -> list[Tenant]:
        return list((await self.session.execute(select(Tenant))).scalars().all())


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()
        return user

    async def get_by_email(self, tenant_id: str, email: str) -> User | None:
        stmt = select(User).where(
            User.tenant_id == tenant_id, User.email == email
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get(self, user_id: str) -> User | None:
        return await self.session.get(User, user_id)


class APIKeyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, key: APIKey) -> APIKey:
        self.session.add(key)
        await self.session.flush()
        return key

    async def get_by_prefix(self, prefix: str) -> APIKey | None:
        stmt = select(APIKey).where(
            APIKey.prefix == prefix, APIKey.revoked == False  # noqa: E712
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def touch(self, key: APIKey) -> None:
        key.last_used_at = _now()
        self.session.add(key)
        await self.session.flush()

    async def revoke(self, key_id: str) -> bool:
        key = await self.session.get(APIKey, key_id)
        if key is None:
            return False
        key.revoked = True
        self.session.add(key)
        await self.session.flush()
        return True


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

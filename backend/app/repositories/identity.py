"""Identity & tenancy repositories: tenants, users, API keys."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import APIKey, Role, Tenant, TenantMembership, User


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


class MembershipRepository:
    """Cross-tenant memberships: which tenants a user can operate in, and the
    role they hold in each. Used to authorize tenant switching and to build the
    effective tenant list in /me."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, user_id: str, tenant_id: str, role: Role) -> TenantMembership:
        m = TenantMembership(user_id=user_id, tenant_id=tenant_id, role=role)
        self.session.add(m)
        await self.session.flush()
        return m

    async def for_user(self, user_id: str) -> list[TenantMembership]:
        stmt = select(TenantMembership).where(TenantMembership.user_id == user_id)
        return list((await self.session.execute(stmt)).scalars().all())

    async def get(self, user_id: str, tenant_id: str) -> TenantMembership | None:
        stmt = select(TenantMembership).where(
            TenantMembership.user_id == user_id,
            TenantMembership.tenant_id == tenant_id,
        )
        return (await self.session.execute(stmt)).scalars().first()

    async def remove(self, user_id: str, tenant_id: str) -> bool:
        m = await self.get(user_id, tenant_id)
        if m is None:
            return False
        await self.session.delete(m)
        await self.session.flush()
        return True

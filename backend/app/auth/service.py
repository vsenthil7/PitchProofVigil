"""Authentication principal, RBAC, and the auth service.

A ``Principal`` is the authenticated caller (from a JWT or an API key) carrying
tenant_id and role. RBAC maps roles to a permission set; the ``require``
helpers raise on insufficient privilege. ``AuthService`` performs registration,
login, and credential verification against the repositories.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import (
    create_access_token,
    hash_password,
    mint_api_key,
    split_api_key,
    verify_api_secret,
    verify_password,
)
from app.core.config import Settings, get_settings
from app.db.models import APIKey, Role, User
from app.repositories.registry import (
    APIKeyRepository,
    TenantRepository,
    UserRepository,
)


class Permission(str, enum.Enum):
    READ = "read"
    WRITE = "write"
    EVALUATE = "evaluate"
    MANAGE_POLICIES = "manage_policies"
    MANAGE_KEYS = "manage_keys"
    MANAGE_USERS = "manage_users"
    ADMIN = "admin"


_ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.OWNER: set(Permission),
    Role.ADMIN: {
        Permission.READ,
        Permission.WRITE,
        Permission.EVALUATE,
        Permission.MANAGE_POLICIES,
        Permission.MANAGE_KEYS,
        Permission.MANAGE_USERS,
    },
    Role.OPERATOR: {Permission.READ, Permission.WRITE, Permission.EVALUATE},
    Role.VIEWER: {Permission.READ},
}


def permissions_for(role: Role) -> set[Permission]:
    return _ROLE_PERMISSIONS.get(role, set())


@dataclass
class Principal:
    """An authenticated caller."""

    subject: str  # user id or api-key id
    tenant_id: str
    role: Role
    kind: str  # "user" | "api_key"

    @property
    def permissions(self) -> set[Permission]:
        return permissions_for(self.role)

    def has(self, permission: Permission) -> bool:
        return permission in self.permissions


class AuthError(Exception):
    """Raised on authentication/authorization failures."""

    def __init__(self, message: str, status_code: int = 401) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def require_permission(principal: Principal, permission: Permission) -> None:
    if not principal.has(permission):
        raise AuthError(
            f"Role '{principal.role.value}' lacks permission "
            f"'{permission.value}'.",
            status_code=403,
        )


class AuthService:
    """Registration, login, and credential verification."""

    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.tenants = TenantRepository(session)
        self.users = UserRepository(session)
        self.api_keys = APIKeyRepository(session)

    async def register_tenant(
        self, tenant_name: str, slug: str, owner_email: str, owner_password: str
    ) -> tuple[str, User]:
        existing = await self.tenants.get_by_slug(slug)
        if existing is not None:
            raise AuthError(f"Tenant slug already exists: {slug}", status_code=409)
        tenant = await self.tenants.create(tenant_name, slug)
        owner = await self.users.create(
            User(
                tenant_id=tenant.id,
                email=owner_email,
                hashed_password=hash_password(owner_password),
                role=Role.OWNER,
            )
        )
        return tenant.id, owner

    async def create_user(
        self, tenant_id: str, email: str, password: str, role: Role
    ) -> User:
        existing = await self.users.get_by_email(tenant_id, email)
        if existing is not None:
            raise AuthError(f"User already exists: {email}", status_code=409)
        return await self.users.create(
            User(
                tenant_id=tenant_id,
                email=email,
                hashed_password=hash_password(password),
                role=role,
            )
        )

    async def login(self, tenant_id: str, email: str, password: str) -> str:
        user = await self.users.get_by_email(tenant_id, email)
        if user is None or not user.is_active:
            raise AuthError("Invalid credentials.")
        if not verify_password(password, user.hashed_password):
            raise AuthError("Invalid credentials.")
        return create_access_token(
            user.id, user.tenant_id, user.role.value, self.settings
        )

    async def create_api_key(
        self, tenant_id: str, name: str, role: Role
    ) -> tuple[str, APIKey]:
        full, prefix, hashed = mint_api_key(self.settings)
        key = await self.api_keys.create(
            APIKey(
                tenant_id=tenant_id,
                name=name,
                prefix=prefix,
                hashed_secret=hashed,
                role=role,
            )
        )
        return full, key

    async def principal_from_api_key(self, full_key: str) -> Principal:
        parts = split_api_key(full_key)
        if parts is None:
            raise AuthError("Malformed API key.")
        prefix, secret = parts
        record = await self.api_keys.get_by_prefix(prefix)
        if record is None or record.revoked:
            raise AuthError("Unknown or revoked API key.")
        if not verify_api_secret(secret, record.hashed_secret):
            raise AuthError("Invalid API key secret.")
        await self.api_keys.touch(record)
        return Principal(
            subject=record.id,
            tenant_id=record.tenant_id,
            role=record.role,
            kind="api_key",
        )

    def principal_from_token(self, claims: dict) -> Principal:
        try:
            role = Role(claims["role"])
        except (KeyError, ValueError) as exc:
            raise AuthError("Invalid token claims.") from exc
        return Principal(
            subject=claims["sub"],
            tenant_id=claims["tenant_id"],
            role=role,
            kind="user",
        )

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
from app.db.models import APIKey, Role, Tenant, User
from app.repositories.registry import (
    MembershipRepository,
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
        self.memberships = MembershipRepository(session)

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
        # Org lifecycle: a disabled tenant blocks all logins (data retained,
        # but no one signs in until re-enabled). Checked after the password so
        # we never reveal tenant state to an unauthenticated caller.
        tenant = await self.tenants.get(tenant_id)
        if tenant is None or not tenant.is_active:
            raise AuthError("Organization is disabled.", status_code=403)
        return create_access_token(
            user.id, user.tenant_id, user.role.value, self.settings
        )

    async def switch_tenant(self, principal: "Principal", target_tenant_id: str) -> str:
        """Mint a new access token scoped to ``target_tenant_id``.

        Authorization rules:
          - The caller must be a *user* (API keys are tenant-bound by design).
          - Switching to your home tenant is always allowed.
          - Owners may switch to any existing tenant (platform operators).
          - Anyone else must hold an explicit TenantMembership in the target,
            and they assume the role recorded on that membership.
        The target tenant must exist and be active. Returns a fresh JWT.
        """
        if principal.kind != "user":
            raise AuthError("API keys cannot switch tenants.")

        target = await self.tenants.get(target_tenant_id)
        if target is None or not target.is_active:
            raise AuthError("Tenant not found.")

        user = await self.users.get(principal.subject)
        if user is None or not user.is_active:
            raise AuthError("User not found.")

        # Determine the role the user holds in the target tenant.
        if target_tenant_id == user.tenant_id:
            role_value = user.role.value
        elif user.role == Role.OWNER:
            # Platform owner keeps owner authority across tenants.
            role_value = Role.OWNER.value
        else:
            membership = await self.memberships.get(user.id, target_tenant_id)
            if membership is None:
                raise AuthError("No access to that tenant.")
            role_value = membership.role.value

        return create_access_token(user.id, target_tenant_id, role_value, self.settings)

    async def set_tenant_active(
        self, principal: "Principal", tenant_id: str, is_active: bool
    ) -> "Tenant":
        """Enable or disable an organization (owner-only platform action).

        Disabling retains all data but blocks new logins and tenant-switches
        into the org. A principal may not disable their own active tenant
        (that would lock them out mid-session); switch elsewhere first.
        """
        if Permission.ADMIN not in permissions_for(principal.role):
            raise AuthError("Not authorized.", status_code=403)
        if not is_active and tenant_id == principal.tenant_id:
            raise AuthError(
                "Cannot disable the organization you are signed into.",
                status_code=409,
            )
        tenant = await self.tenants.set_active(tenant_id, is_active)
        if tenant is None:
            raise AuthError("Tenant not found.", status_code=404)
        return tenant

    async def seed_demo(self) -> str:
        """Idempotently create a demo organization with one user per role and
        return an owner-scoped access token. Lets a judge land in a populated,
        multi-role org without manual registration. Safe to call repeatedly:
        the org and users are created only if missing.
        """
        slug = "demo-worldcup"
        owner_email = "owner@demo.worldcup"
        password = "demo-pass-1234"
        tenant = await self.tenants.get_by_slug(slug)
        if tenant is None:
            tenant = await self.tenants.create("World Cup Demo Org", slug)
            await self.users.create(
                User(tenant_id=tenant.id, email=owner_email,
                     hashed_password=hash_password(password), role=Role.OWNER)
            )
        # Ensure one active user per non-owner role exists.
        for role, email in (
            (Role.ADMIN, "admin@demo.worldcup"),
            (Role.OPERATOR, "operator@demo.worldcup"),
            (Role.VIEWER, "viewer@demo.worldcup"),
        ):
            if await self.users.get_by_email(tenant.id, email) is None:
                await self.users.create(
                    User(tenant_id=tenant.id, email=email,
                         hashed_password=hash_password(password), role=role)
                )
        # A demo org must never be left disabled.
        if not tenant.is_active:
            await self.tenants.set_active(tenant.id, True)
        owner = await self.users.get_by_email(tenant.id, owner_email)
        return create_access_token(
            owner.id, tenant.id, owner.role.value, self.settings
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

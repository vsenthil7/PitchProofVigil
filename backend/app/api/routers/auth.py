"""Auth router: register, login, users, API keys."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session, get_principal, get_settings_dep, require
from app.api.schemas import (
    APIKeyResponse,
    CreateAPIKeyRequest,
    CreateUserRequest,
    GrantMembershipRequest,
    LoginRequest,
    MeResponse,
    RegisterRequest,
    RegisterResponse,
    SwitchTenantRequest,
    TenantSummary,
    TokenResponse,
)
from app.auth.service import AuthError, AuthService, Permission, Principal
from app.core.config import Settings
from app.db.models import Role
from app.repositories.identity import (
    MembershipRepository,
    TenantRepository,
    UserRepository,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse, status_code=201)
async def register(
    body: RegisterRequest,
    session: AsyncSession = Depends(db_session),
    settings: Settings = Depends(get_settings_dep),
) -> RegisterResponse:
    auth = AuthService(session, settings)
    try:
        tenant_id, owner = await auth.register_tenant(
            body.tenant_name, body.slug, body.owner_email, body.owner_password
        )
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    return RegisterResponse(tenant_id=tenant_id, owner_id=owner.id)


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    session: AsyncSession = Depends(db_session),
    settings: Settings = Depends(get_settings_dep),
) -> TokenResponse:
    auth = AuthService(session, settings)
    try:
        token = await auth.login(body.tenant_id, body.email, body.password)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=MeResponse)
async def me(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(db_session),
) -> MeResponse:
    """The authenticated caller's identity — role, tenant, and visible tenants.

    Owners can see (and switch to) every tenant; everyone else sees only their
    own. This is what lets the UI render a role badge and a tenant switcher
    without inventing data the backend doesn't actually authorize.
    """
    tenants_repo = TenantRepository(session)
    users_repo = UserRepository(session)
    memberships_repo = MembershipRepository(session)

    current = await tenants_repo.get(principal.tenant_id)
    tenant_name = current.name if current else principal.tenant_id

    email: str | None = None
    home_tenant_id: str | None = None
    if principal.kind == "user":
        user = await users_repo.get(principal.subject)
        if user:
            email = user.email
            home_tenant_id = user.tenant_id

    if principal.role == Role.OWNER:
        # Platform owners can see and switch to every tenant.
        visible = await tenants_repo.list()
    else:
        # Effective set = home tenant ∪ explicit memberships.
        ids: list[str] = []
        if home_tenant_id:
            ids.append(home_tenant_id)
        else:
            ids.append(principal.tenant_id)
        if principal.kind == "user":
            for m in await memberships_repo.for_user(principal.subject):
                if m.tenant_id not in ids:
                    ids.append(m.tenant_id)
        visible = []
        for tid in ids:
            t = await tenants_repo.get(tid)
            if t is not None:
                visible.append(t)

    return MeResponse(
        subject=principal.subject,
        kind=principal.kind,
        email=email,
        role=principal.role,
        tenant_id=principal.tenant_id,
        tenant_name=tenant_name,
        tenants=[TenantSummary(id=t.id, name=t.name, slug=t.slug) for t in visible],
    )


@router.post("/switch-tenant", response_model=TokenResponse)
async def switch_tenant(
    body: SwitchTenantRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(db_session),
    settings: Settings = Depends(get_settings_dep),
) -> TokenResponse:
    """Re-issue a token scoped to another tenant the caller may access.

    Owners can switch to any tenant; other users need an explicit membership.
    The returned token carries the role the caller holds in the target tenant.
    """
    auth = AuthService(session, settings)
    try:
        token = await auth.switch_tenant(principal, body.tenant_id)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    return TokenResponse(access_token=token)


@router.get("/tenants", response_model=list[TenantSummary])
async def list_tenants(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(db_session),
) -> list[TenantSummary]:
    """Tenants the caller may view. Owners: all; others: home ∪ memberships."""
    tenants_repo = TenantRepository(session)
    if principal.role == Role.OWNER:
        tenants = await tenants_repo.list()
    else:
        memberships_repo = MembershipRepository(session)
        ids: list[str] = [principal.tenant_id]
        if principal.kind == "user":
            for m in await memberships_repo.for_user(principal.subject):
                if m.tenant_id not in ids:
                    ids.append(m.tenant_id)
        tenants = []
        for tid in ids:
            t = await tenants_repo.get(tid)
            if t is not None:
                tenants.append(t)
    return [TenantSummary(id=t.id, name=t.name, slug=t.slug) for t in tenants]


@router.post("/users", status_code=201)
async def create_user(
    body: CreateUserRequest,
    principal: Principal = Depends(require(Permission.MANAGE_USERS)),
    session: AsyncSession = Depends(db_session),
    settings: Settings = Depends(get_settings_dep),
) -> dict:
    auth = AuthService(session, settings)
    try:
        user = await auth.create_user(
            principal.tenant_id, body.email, body.password, body.role
        )
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    return {"id": user.id, "email": user.email, "role": user.role.value}


@router.post("/memberships", status_code=201)
async def grant_membership(
    body: GrantMembershipRequest,
    principal: Principal = Depends(require(Permission.MANAGE_USERS)),
    session: AsyncSession = Depends(db_session),
) -> dict:
    """Grant a user access to a tenant (cross-tenant membership).

    Requires MANAGE_USERS. Idempotent on (user_id, tenant_id): re-granting
    updates the role rather than erroring. This is what lets a non-owner
    operate across tenants and is the backing store for /me's tenant list.
    """
    users_repo = UserRepository(session)
    tenants_repo = TenantRepository(session)
    memberships_repo = MembershipRepository(session)

    target_user = await users_repo.get(body.user_id)
    if target_user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    target_tenant = await tenants_repo.get(body.tenant_id)
    if target_tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found.")

    existing = await memberships_repo.get(body.user_id, body.tenant_id)
    if existing is not None:
        existing.role = body.role
        await session.flush()
        membership = existing
    else:
        membership = await memberships_repo.add(body.user_id, body.tenant_id, body.role)
    return {
        "id": membership.id,
        "user_id": membership.user_id,
        "tenant_id": membership.tenant_id,
        "role": membership.role.value,
    }


@router.post("/api-keys", response_model=APIKeyResponse, status_code=201)
async def create_api_key(
    body: CreateAPIKeyRequest,
    principal: Principal = Depends(require(Permission.MANAGE_KEYS)),
    session: AsyncSession = Depends(db_session),
    settings: Settings = Depends(get_settings_dep),
) -> APIKeyResponse:
    auth = AuthService(session, settings)
    full, key = await auth.create_api_key(principal.tenant_id, body.name, body.role)
    return APIKeyResponse(
        id=key.id, name=key.name, prefix=key.prefix, role=key.role, api_key=full
    )

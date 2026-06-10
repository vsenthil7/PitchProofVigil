"""Auth router: register, login, users, API keys."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session, get_settings_dep, require
from app.api.schemas import (
    APIKeyResponse,
    CreateAPIKeyRequest,
    CreateUserRequest,
    LoginRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
)
from app.auth.service import AuthError, AuthService, Permission, Principal
from app.core.config import Settings

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

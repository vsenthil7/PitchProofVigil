"""Tests for the auth service, principals, and RBAC."""
from __future__ import annotations

import pytest

from app.auth.security import decode_access_token
from app.auth.service import (
    AuthError,
    AuthService,
    Permission,
    Principal,
    permissions_for,
    require_permission,
)
from app.core.config import Settings
from app.db.models import Role

SETTINGS = Settings(jwt_secret="test-secret")


def _svc(session):
    return AuthService(session, SETTINGS)


# ---- RBAC matrix ----

def test_permissions_for_roles():
    assert Permission.ADMIN in permissions_for(Role.OWNER)
    assert Permission.MANAGE_USERS in permissions_for(Role.ADMIN)
    assert Permission.ADMIN not in permissions_for(Role.ADMIN)
    assert permissions_for(Role.OPERATOR) == {
        Permission.READ,
        Permission.WRITE,
        Permission.EVALUATE,
    }
    assert permissions_for(Role.VIEWER) == {Permission.READ}


def test_principal_has_and_require():
    p = Principal(subject="u", tenant_id="t", role=Role.VIEWER, kind="user")
    assert p.has(Permission.READ)
    assert not p.has(Permission.WRITE)
    require_permission(p, Permission.READ)  # no raise
    with pytest.raises(AuthError) as ei:
        require_permission(p, Permission.WRITE)
    assert ei.value.status_code == 403


# ---- Registration / login ----

async def test_register_and_login(db):
    async with db.session() as s:
        svc = _svc(s)
        tid, owner = await svc.register_tenant("Acme", "acme", "o@a.com", "pw123456")
        assert owner.role == Role.OWNER
    async with db.session() as s:
        svc = _svc(s)
        token = await svc.login(tid, "o@a.com", "pw123456")
        claims = decode_access_token(token, SETTINGS)
        assert claims["tenant_id"] == tid
        p = svc.principal_from_token(claims)
        assert p.role == Role.OWNER and p.kind == "user"


async def test_register_duplicate_slug(db):
    async with db.session() as s:
        svc = _svc(s)
        await svc.register_tenant("Acme", "acme", "o@a.com", "pw123456")
    async with db.session() as s:
        svc = _svc(s)
        with pytest.raises(AuthError) as ei:
            await svc.register_tenant("Acme2", "acme", "x@a.com", "pw123456")
        assert ei.value.status_code == 409


async def test_login_bad_password(db, tenant_id):
    async with db.session() as s:
        svc = _svc(s)
        await svc.create_user(tenant_id, "u@a.com", "rightpw12", Role.OPERATOR)
    async with db.session() as s:
        svc = _svc(s)
        with pytest.raises(AuthError):
            await svc.login(tenant_id, "u@a.com", "wrongpw12")


async def test_login_unknown_user(db, tenant_id):
    async with db.session() as s:
        svc = _svc(s)
        with pytest.raises(AuthError):
            await svc.login(tenant_id, "ghost@a.com", "pw")


async def test_create_user_duplicate(db, tenant_id):
    async with db.session() as s:
        svc = _svc(s)
        await svc.create_user(tenant_id, "u@a.com", "pw123456", Role.VIEWER)
    async with db.session() as s:
        svc = _svc(s)
        with pytest.raises(AuthError) as ei:
            await svc.create_user(tenant_id, "u@a.com", "pw123456", Role.VIEWER)
        assert ei.value.status_code == 409


# ---- API keys ----

async def test_api_key_create_and_auth(db, tenant_id):
    async with db.session() as s:
        svc = _svc(s)
        full, key = await svc.create_api_key(tenant_id, "ci", Role.OPERATOR)
    async with db.session() as s:
        svc = _svc(s)
        p = await svc.principal_from_api_key(full)
        assert p.kind == "api_key"
        assert p.tenant_id == tenant_id
        assert p.role == Role.OPERATOR


async def test_api_key_malformed(db):
    async with db.session() as s:
        svc = _svc(s)
        with pytest.raises(AuthError):
            await svc.principal_from_api_key("no-dot-here")


async def test_api_key_unknown(db):
    async with db.session() as s:
        svc = _svc(s)
        with pytest.raises(AuthError):
            await svc.principal_from_api_key("ppv_dead.beefsecret")


async def test_api_key_wrong_secret(db, tenant_id):
    async with db.session() as s:
        svc = _svc(s)
        full, key = await svc.create_api_key(tenant_id, "ci", Role.OPERATOR)
        prefix = full.split(".")[0]
    async with db.session() as s:
        svc = _svc(s)
        with pytest.raises(AuthError):
            await svc.principal_from_api_key(f"{prefix}.totallywrongsecret")


# ---- Token claims ----

def test_principal_from_token_bad_role():
    svc = AuthService(session=None, settings=SETTINGS)  # no DB needed
    with pytest.raises(AuthError):
        svc.principal_from_token({"sub": "u", "tenant_id": "t", "role": "wizard"})


def test_principal_from_token_missing_claim():
    svc = AuthService(session=None, settings=SETTINGS)
    with pytest.raises(AuthError):
        svc.principal_from_token({"sub": "u", "tenant_id": "t"})

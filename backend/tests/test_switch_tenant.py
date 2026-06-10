"""Tests for tenant switching, memberships, and the richer readiness checks."""
from __future__ import annotations


from app.db.models import Role
from app.observability.health import HealthService
from app.repositories.identity import MembershipRepository


# ---- switch-tenant endpoint ----

def _make_second_tenant(client, headers):
    # Owner registers a second org via the public register endpoint, then we
    # operate as the original owner switching into it (owners span all tenants).
    r = client.post(
        "/api/auth/register",
        json={"tenant_name": "Second Org", "slug": "second-org",
              "owner_email": "o2@org.com", "owner_password": "pw12345678"},
    )
    return r.json()["tenant_id"]


def test_owner_can_switch_to_any_tenant(owner_auth):
    client, headers, tenant_id = owner_auth
    other = _make_second_tenant(client, headers)
    r = client.post("/api/auth/switch-tenant", headers=headers, json={"tenant_id": other})
    assert r.status_code == 200
    new_token = r.json()["access_token"]
    # The new token is scoped to the other tenant.
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {new_token}"}).json()
    assert me["tenant_id"] == other
    assert me["role"] == "owner"  # platform owner keeps owner authority


def test_switch_to_home_tenant_is_allowed(owner_auth):
    client, headers, tenant_id = owner_auth
    r = client.post("/api/auth/switch-tenant", headers=headers, json={"tenant_id": tenant_id})
    assert r.status_code == 200


def test_switch_to_unknown_tenant_rejected(owner_auth):
    client, headers, _ = owner_auth
    r = client.post("/api/auth/switch-tenant", headers=headers, json={"tenant_id": "nope"})
    assert r.status_code in (400, 401, 404)


def test_non_owner_without_membership_denied(owner_auth):
    client, headers, tenant_id = owner_auth
    other = _make_second_tenant(client, headers)
    # Create a viewer in the home tenant.
    client.post("/api/auth/users", headers=headers,
                json={"email": "v@org.com", "password": "pw12345678", "role": "viewer"})
    tok = client.post("/api/auth/login",
                      json={"tenant_id": tenant_id, "email": "v@org.com", "password": "pw12345678"}).json()["access_token"]
    vh = {"Authorization": f"Bearer {tok}"}
    # Viewer has no membership in `other` → denied.
    r = client.post("/api/auth/switch-tenant", headers=vh, json={"tenant_id": other})
    assert r.status_code in (401, 403)


def test_api_key_cannot_switch(owner_auth):
    client, headers, tenant_id = owner_auth
    other = _make_second_tenant(client, headers)
    key = client.post("/api/auth/api-keys", headers=headers,
                      json={"name": "k", "role": "operator"}).json()["api_key"]
    r = client.post("/api/auth/switch-tenant", headers={"X-API-Key": key},
                    json={"tenant_id": other})
    assert r.status_code in (401, 403)


# ---- membership repository ----

async def test_membership_repo_add_get_remove(db, tenant_id):
    async with db.session() as s:
        repo = MembershipRepository(s)
        m = await repo.add("user-x", "tenant-y", Role.OPERATOR)
        assert m.role == Role.OPERATOR
    async with db.session() as s:
        repo = MembershipRepository(s)
        got = await repo.get("user-x", "tenant-y")
        assert got is not None and got.tenant_id == "tenant-y"
        rows = await repo.for_user("user-x")
        assert len(rows) == 1
    async with db.session() as s:
        repo = MembershipRepository(s)
        assert await repo.remove("user-x", "tenant-y") is True
        assert await repo.remove("user-x", "tenant-y") is False


async def test_member_with_membership_sees_tenant_in_me(owner_auth, db):
    client, headers, tenant_id = owner_auth
    other = _make_second_tenant(client, headers)
    # Create an operator in home tenant.
    client.post("/api/auth/users", headers=headers,
                json={"email": "op@org.com", "password": "pw12345678", "role": "operator"})
    tok = client.post("/api/auth/login",
                      json={"tenant_id": tenant_id, "email": "op@org.com", "password": "pw12345678"}).json()["access_token"]
    me_before = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tok}"}).json()
    user_id = me_before["subject"]
    assert other not in [t["id"] for t in me_before["tenants"]]

    # Owner grants the operator a viewer membership in `other` via the API.
    grant = client.post("/api/auth/memberships", headers=headers,
                        json={"user_id": user_id, "tenant_id": other, "role": "viewer"})
    assert grant.status_code == 201

    me_after = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tok}"}).json()
    assert other in [t["id"] for t in me_after["tenants"]]
    # And now they can switch into it, assuming the membership role.
    r = client.post("/api/auth/switch-tenant",
                    headers={"Authorization": f"Bearer {tok}"}, json={"tenant_id": other})
    assert r.status_code == 200
    me_switched = client.get("/api/auth/me",
                             headers={"Authorization": f"Bearer {r.json()['access_token']}"}).json()
    assert me_switched["tenant_id"] == other
    assert me_switched["role"] == "viewer"


# ---- readiness checks ----

async def test_readiness_includes_encryption_and_migrations(db, api_settings):
    hs = HealthService(db, settings=api_settings)
    report = await hs.readiness()
    names = {c.name for c in report.checks}
    assert {"database", "encryption", "migrations"} <= names
    assert report.ready is True


def test_ready_endpoint_reports_checks(client):
    r = client.get("/ready")
    assert r.status_code == 200
    body = r.json()
    names = {c["name"] for c in body["checks"]}
    assert "encryption" in names and "migrations" in names


def test_grant_membership_unknown_user_404(owner_auth):
    client, headers, tenant_id = owner_auth
    r = client.post("/api/auth/memberships", headers=headers,
                    json={"user_id": "nope", "tenant_id": tenant_id, "role": "viewer"})
    assert r.status_code == 404


def test_grant_membership_unknown_tenant_404(owner_auth):
    client, headers, tenant_id = owner_auth
    me = client.get("/api/auth/me", headers=headers).json()
    r = client.post("/api/auth/memberships", headers=headers,
                    json={"user_id": me["subject"], "tenant_id": "nope", "role": "viewer"})
    assert r.status_code == 404


def test_grant_membership_is_idempotent_and_updates_role(owner_auth):
    client, headers, tenant_id = owner_auth
    other = _make_second_tenant(client, headers)
    client.post("/api/auth/users", headers=headers,
                json={"email": "u2@org.com", "password": "pw12345678", "role": "operator"})
    tok = client.post("/api/auth/login",
                      json={"tenant_id": tenant_id, "email": "u2@org.com", "password": "pw12345678"}).json()["access_token"]
    uid = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tok}"}).json()["subject"]
    r1 = client.post("/api/auth/memberships", headers=headers,
                     json={"user_id": uid, "tenant_id": other, "role": "viewer"})
    assert r1.status_code == 201 and r1.json()["role"] == "viewer"
    r2 = client.post("/api/auth/memberships", headers=headers,
                     json={"user_id": uid, "tenant_id": other, "role": "operator"})
    assert r2.status_code == 201 and r2.json()["role"] == "operator"
    assert r1.json()["id"] == r2.json()["id"]


def test_grant_membership_requires_manage_users(owner_auth):
    client, headers, tenant_id = owner_auth
    other = _make_second_tenant(client, headers)
    client.post("/api/auth/users", headers=headers,
                json={"email": "v3@org.com", "password": "pw12345678", "role": "viewer"})
    tok = client.post("/api/auth/login",
                      json={"tenant_id": tenant_id, "email": "v3@org.com", "password": "pw12345678"}).json()["access_token"]
    r = client.post("/api/auth/memberships", headers={"Authorization": f"Bearer {tok}"},
                    json={"user_id": "x", "tenant_id": other, "role": "viewer"})
    assert r.status_code == 403


def test_tenants_endpoint_for_non_owner_with_membership(owner_auth):
    client, headers, tenant_id = owner_auth
    other = _make_second_tenant(client, headers)
    client.post("/api/auth/users", headers=headers,
                json={"email": "tl@org.com", "password": "pw12345678", "role": "operator"})
    tok = client.post("/api/auth/login",
                      json={"tenant_id": tenant_id, "email": "tl@org.com", "password": "pw12345678"}).json()["access_token"]
    uid = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tok}"}).json()["subject"]
    client.post("/api/auth/memberships", headers=headers,
                json={"user_id": uid, "tenant_id": other, "role": "viewer"})
    # /tenants for the non-owner returns home ∪ membership.
    tlist = client.get("/api/auth/tenants", headers={"Authorization": f"Bearer {tok}"}).json()
    ids = {t["id"] for t in tlist}
    assert tenant_id in ids and other in ids


async def test_readiness_against_migrated_db(api_settings, tmp_path):
    """Run readiness against a real Alembic-migrated SQLite file so the
    migration-head success branch (db version == head) is exercised."""
    import subprocess, sys, os
    from app.db.engine import Database

    db_path = tmp_path / "ready.db"
    dsn = f"sqlite+aiosqlite:///{db_path}"
    env = {**os.environ, "DATABASE_DSN": dsn}
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"],
                   check=True, env=env, capture_output=True)

    from dataclasses import replace
    settings = replace(api_settings, database_dsn=dsn)
    db = Database(settings)
    from app.observability.health import HealthService
    report = await HealthService(db, settings=settings).readiness()
    migration_check = next(c for c in report.checks if c.name == "migrations")
    assert migration_check.healthy is True
    assert migration_check.detail == "at head"
    await db.engine.dispose()


async def test_switch_tenant_user_not_found(api_settings):
    """switch_tenant guards against a token whose subject no longer exists."""
    from app.db.engine import Database
    from app.auth.service import AuthError, AuthService, Principal
    from app.db.models import Role

    db = Database(api_settings)
    # Build schema + a tenant to switch to.
    async with db.engine.begin() as conn:
        from sqlmodel import SQLModel
        await conn.run_sync(SQLModel.metadata.create_all)
    async with db.session() as s:
        from app.repositories.identity import TenantRepository
        t = await TenantRepository(s).create("Ghost Org", "ghost-org")
        await s.commit()
        target = t.id
    principal = Principal(kind="user", subject="missing-user", tenant_id=target, role=Role.OWNER)
    async with db.session() as s:
        svc = AuthService(s, api_settings)
        try:
            await svc.switch_tenant(principal, target)
            assert False, "expected AuthError"
        except AuthError as e:
            assert "User not found" in e.message
    await db.engine.dispose()


def test_head_revision_returns_none_on_bad_config(monkeypatch):
    """The migration-head resolver degrades gracefully if Alembic config is
    unreachable at runtime (returns None rather than raising)."""
    import app.db.migrations_info as mi
    mi.head_revision.cache_clear()

    class Boom:
        @staticmethod
        def from_config(_cfg):
            raise RuntimeError("no config")

    monkeypatch.setattr(mi, "ScriptDirectory", Boom, raising=False)
    # Also ensure the import path inside the function picks up the patched name.
    monkeypatch.setattr("alembic.script.ScriptDirectory", Boom, raising=False)
    assert mi.head_revision() is None
    mi.head_revision.cache_clear()

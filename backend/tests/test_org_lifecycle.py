"""Org lifecycle: enable/disable organizations (owner-only)."""
from __future__ import annotations

from app.repositories.identity import TenantRepository


def _second_org(client):
    r = client.post(
        "/api/auth/register",
        json={"tenant_name": "Second", "slug": "second-org",
              "owner_email": "o2@org.com", "owner_password": "pw12345678"},
    )
    return r.json()["tenant_id"]


def test_owner_can_disable_and_enable_other_org(owner_auth):
    client, headers, _ = owner_auth
    other = _second_org(client)
    r = client.patch(f"/api/auth/tenants/{other}/active", headers=headers, json={"is_active": False})
    assert r.status_code == 200
    assert r.json()["is_active"] is False
    r2 = client.patch(f"/api/auth/tenants/{other}/active", headers=headers, json={"is_active": True})
    assert r2.status_code == 200
    assert r2.json()["is_active"] is True


def test_cannot_disable_own_active_org(owner_auth):
    client, headers, tenant_id = owner_auth
    r = client.patch(f"/api/auth/tenants/{tenant_id}/active", headers=headers, json={"is_active": False})
    assert r.status_code == 409


def test_disable_unknown_tenant_404(owner_auth):
    client, headers, _ = owner_auth
    r = client.patch("/api/auth/tenants/nope/active", headers=headers, json={"is_active": False})
    assert r.status_code == 404


def test_non_owner_cannot_disable_org(owner_auth):
    client, headers, tenant_id = owner_auth
    other = _second_org(client)
    client.post("/api/auth/users", headers=headers, json={"email": "adm@org.com", "password": "pw12345678", "role": "admin"})
    tok = client.post("/api/auth/login", json={"tenant_id": tenant_id, "email": "adm@org.com", "password": "pw12345678"}).json()["access_token"]
    ah = {"Authorization": "Bearer " + tok}
    r = client.patch(f"/api/auth/tenants/{other}/active", headers=ah, json={"is_active": False})
    assert r.status_code == 403


def test_login_blocked_for_disabled_org(owner_auth):
    client, headers, _ = owner_auth
    other = _second_org(client)
    client.patch(f"/api/auth/tenants/{other}/active", headers=headers, json={"is_active": False})
    r = client.post("/api/auth/login", json={"tenant_id": other, "email": "o2@org.com", "password": "pw12345678"})
    assert r.status_code == 403
    assert "disabled" in r.json()["error"]["message"].lower()


def test_login_works_after_reenable(owner_auth):
    client, headers, _ = owner_auth
    other = _second_org(client)
    client.patch(f"/api/auth/tenants/{other}/active", headers=headers, json={"is_active": False})
    client.patch(f"/api/auth/tenants/{other}/active", headers=headers, json={"is_active": True})
    r = client.post("/api/auth/login", json={"tenant_id": other, "email": "o2@org.com", "password": "pw12345678"})
    assert r.status_code == 200


def test_switch_into_disabled_org_blocked(owner_auth):
    client, headers, _ = owner_auth
    other = _second_org(client)
    client.patch(f"/api/auth/tenants/{other}/active", headers=headers, json={"is_active": False})
    r = client.post("/api/auth/switch-tenant", headers=headers, json={"tenant_id": other})
    assert r.status_code in (401, 404)


def test_me_and_tenants_carry_is_active(owner_auth):
    client, headers, tenant_id = owner_auth
    me = client.get("/api/auth/me", headers=headers).json()
    assert all("is_active" in t for t in me["tenants"])
    tlist = client.get("/api/auth/tenants", headers=headers).json()
    assert all("is_active" in t for t in tlist)


def test_requires_auth(client):
    r = client.patch("/api/auth/tenants/x/active", json={"is_active": False})
    assert r.status_code == 401


async def test_repo_set_active_unknown_returns_none(db):
    async with db.session() as s:
        repo = TenantRepository(s)
        assert await repo.set_active("missing", False) is None


async def test_repo_set_active_toggles(db, tenant_id):
    async with db.session() as s:
        repo = TenantRepository(s)
        t = await repo.set_active(tenant_id, False)
        assert t is not None and t.is_active is False
    async with db.session() as s:
        repo = TenantRepository(s)
        t = await repo.set_active(tenant_id, True)
        assert t.is_active is True

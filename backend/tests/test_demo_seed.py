"""Demo seed endpoint: one-click populated multi-role org for judges."""
from __future__ import annotations

from app.repositories.identity import TenantRepository, UserRepository


def test_demo_creates_org_and_signs_in_as_owner(client):
    r = client.post("/api/auth/demo")
    assert r.status_code == 200
    tok = r.json()["access_token"]
    me = client.get("/api/auth/me", headers={"Authorization": "Bearer " + tok}).json()
    assert me["role"] == "owner"
    assert me["tenant_name"] == "World Cup Demo Org"


def test_demo_is_idempotent(client):
    a = client.post("/api/auth/demo")
    b = client.post("/api/auth/demo")
    assert a.status_code == 200 and b.status_code == 200
    me_a = client.get("/api/auth/me", headers={"Authorization": "Bearer " + a.json()["access_token"]}).json()
    me_b = client.get("/api/auth/me", headers={"Authorization": "Bearer " + b.json()["access_token"]}).json()
    assert me_a["tenant_id"] == me_b["tenant_id"]


def test_demo_seeds_all_four_roles(client):
    tok = client.post("/api/auth/demo").json()["access_token"]
    me = client.get("/api/auth/me", headers={"Authorization": "Bearer " + tok}).json()
    tid = me["tenant_id"]
    for email, role in (("admin@demo.worldcup", "admin"), ("operator@demo.worldcup", "operator"), ("viewer@demo.worldcup", "viewer")):
        lr = client.post("/api/auth/login", json={"tenant_id": tid, "email": email, "password": "demo-pass-1234"})
        assert lr.status_code == 200
        who = client.get("/api/auth/me", headers={"Authorization": "Bearer " + lr.json()["access_token"]}).json()
        assert who["role"] == role


def test_demo_no_auth_required(client):
    # No Authorization header needed to bootstrap the demo.
    assert client.post("/api/auth/demo").status_code == 200


async def test_demo_reenables_disabled_org(db, api_settings):
    # If a previous run left the demo org disabled, seed_demo re-enables it.
    from app.auth.service import AuthService
    async with db.session() as s:
        await AuthService(s, api_settings).seed_demo()
        await s.commit()
    async with db.session() as s:
        t = await TenantRepository(s).get_by_slug("demo-worldcup")
        await TenantRepository(s).set_active(t.id, False)
        await s.commit()
    async with db.session() as s:
        await AuthService(s, api_settings).seed_demo()
        await s.commit()
    async with db.session() as s:
        t = await TenantRepository(s).get_by_slug("demo-worldcup")
        assert t.is_active is True


async def test_demo_users_persist_across_calls(db, api_settings):
    from app.auth.service import AuthService
    async with db.session() as s:
        await AuthService(s, api_settings).seed_demo()
        await s.commit()
    async with db.session() as s:
        await AuthService(s, api_settings).seed_demo()
        await s.commit()
    async with db.session() as s:
        t = await TenantRepository(s).get_by_slug("demo-worldcup")
        u = await UserRepository(s).get_by_email(t.id, "admin@demo.worldcup")
        assert u is not None

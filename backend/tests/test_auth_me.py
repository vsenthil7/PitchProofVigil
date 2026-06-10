"""Tests for /api/auth/me and /api/auth/tenants (Phase J identity endpoints)."""
from __future__ import annotations


def test_me_returns_owner_identity(owner_auth):
    client, headers, tenant_id = owner_auth
    r = client.get("/api/auth/me", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "user"
    assert body["email"] == "o@wc.com"
    assert body["role"] == "owner"
    assert body["tenant_id"] == tenant_id
    assert body["tenant_name"] == "WC Ops"
    # Owner sees at least their own tenant in the switch list.
    assert any(t["id"] == tenant_id for t in body["tenants"])


def test_me_requires_auth(client):
    assert client.get("/api/auth/me").status_code == 401


def test_tenants_lists_for_owner(owner_auth):
    client, headers, tenant_id = owner_auth
    r = client.get("/api/auth/tenants", headers=headers)
    assert r.status_code == 200
    tenants = r.json()
    assert any(t["id"] == tenant_id and t["slug"] == "wc-ops" for t in tenants)


def test_non_owner_sees_only_own_tenant(owner_auth):
    client, headers, tenant_id = owner_auth
    # Owner creates a viewer in the same tenant.
    client.post(
        "/api/auth/users",
        headers=headers,
        json={"email": "v@wc.com", "password": "pw123456", "role": "viewer"},
    )
    tok = client.post(
        "/api/auth/login",
        json={"tenant_id": tenant_id, "email": "v@wc.com", "password": "pw123456"},
    ).json()["access_token"]
    vheaders = {"Authorization": f"Bearer {tok}"}

    me = client.get("/api/auth/me", headers=vheaders).json()
    assert me["role"] == "viewer"
    assert me["email"] == "v@wc.com"
    # Viewer sees exactly their own tenant — no cross-tenant visibility.
    assert [t["id"] for t in me["tenants"]] == [tenant_id]

    tlist = client.get("/api/auth/tenants", headers=vheaders).json()
    assert [t["id"] for t in tlist] == [tenant_id]


def test_me_works_with_api_key(owner_auth):
    client, headers, tenant_id = owner_auth
    key = client.post(
        "/api/auth/api-keys",
        headers=headers,
        json={"name": "ci", "role": "operator"},
    ).json()["api_key"]
    me = client.get("/api/auth/me", headers={"X-API-Key": key}).json()
    assert me["kind"] == "api_key"
    assert me["role"] == "operator"
    assert me["tenant_id"] == tenant_id
    # API-key principals have no email.
    assert me["email"] is None

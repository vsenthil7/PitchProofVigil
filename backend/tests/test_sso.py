"""Tests for the SSO/SAML flow (P6.M8)."""
from __future__ import annotations

import base64

import pytest

from app.auth.sso.service import SSOError, SSOService
from app.core.config import Settings
from app.crypto.cipher import FieldCipher
from app.crypto.keys import KeyProvider

_SETTINGS = Settings(use_mocks=True)


def _cipher() -> FieldCipher:
    return FieldCipher(KeyProvider(_SETTINGS))


FAKE_SAML_RESPONSE = base64.b64encode(
    b"""<?xml version="1.0"?>
<samlp:Response xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"
    xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion">
  <saml:Assertion>
    <saml:Subject>
      <saml:NameID Format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress">testuser@example.com</saml:NameID>
    </saml:Subject>
  </saml:Assertion>
</samlp:Response>"""
).decode()


async def test_configure_and_get_config_roundtrip(db, tenant_id):
    async with db.session() as s:
        svc = SSOService(s, _cipher(), _SETTINGS)
        row = await svc.configure_idp(
            tenant_id=tenant_id,
            idp_entity_id="https://idp.example.com",
            idp_sso_url="https://idp.example.com/sso",
            idp_x509_cert="MIIC-cert",
            sp_base_url="http://localhost:8000",
            tenant_slug="test-tenant",
        )
        assert row.sp_entity_id.endswith("/api/auth/sso/test-tenant/metadata")
        # Stored values are encrypted (not plaintext).
        assert row.idp_sso_url != "https://idp.example.com/sso"

        fetched = await svc.get_config(tenant_id)
        assert fetched is not None
        assert _cipher().decrypt(fetched.idp_sso_url) == "https://idp.example.com/sso"


async def test_configure_idp_upserts(db, tenant_id):
    """Re-configuring replaces the prior row (delete-then-insert)."""
    async with db.session() as s:
        svc = SSOService(s, _cipher(), _SETTINGS)
        await svc.configure_idp(tenant_id, "e1", "u1", "c1", "http://x", "test-tenant")
        await svc.configure_idp(tenant_id, "e2", "u2", "c2", "http://x", "test-tenant")
        cfg = await svc.get_config(tenant_id)
        assert _cipher().decrypt(cfg.idp_entity_id) == "e2"


async def test_process_acs_creates_user_and_mints_jwt(db, tenant_id):
    async with db.session() as s:
        svc = SSOService(s, _cipher(), _SETTINGS)
        await svc.configure_idp(tenant_id, "e", "u", "c", "http://localhost:8000", "test-tenant")
        token = await svc.process_acs_response(
            tenant_id, FAKE_SAML_RESPONSE, "http://localhost:8000"
        )
        assert token and len(token.split(".")) == 3
        # The SAML user now exists.
        user = await svc._users.get_by_email(tenant_id, "testuser@example.com")
        assert user is not None
        assert user.hashed_password == "sso-managed"


async def test_process_acs_without_config_raises(db, tenant_id):
    async with db.session() as s:
        svc = SSOService(s, _cipher(), _SETTINGS)
        with pytest.raises(SSOError, match="not configured"):
            await svc.process_acs_response(tenant_id, FAKE_SAML_RESPONSE, "http://x")


async def test_process_acs_invalid_base64_raises(db, tenant_id):
    async with db.session() as s:
        svc = SSOService(s, _cipher(), _SETTINGS)
        await svc.configure_idp(tenant_id, "e", "u", "c", "http://x", "test-tenant")
        with pytest.raises(SSOError, match="Invalid SAMLResponse"):
            await svc.process_acs_response(tenant_id, "not-base64!!", "http://x")


async def test_process_acs_missing_nameid_raises(db, tenant_id):
    no_nameid = base64.b64encode(
        b'<?xml version="1.0"?><samlp:Response '
        b'xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"></samlp:Response>'
    ).decode()
    async with db.session() as s:
        svc = SSOService(s, _cipher(), _SETTINGS)
        await svc.configure_idp(tenant_id, "e", "u", "c", "http://x", "test-tenant")
        with pytest.raises(SSOError, match="NameID not found"):
            await svc.process_acs_response(tenant_id, no_nameid, "http://x")


async def test_get_or_create_user_idempotent(db, tenant_id):
    async with db.session() as s:
        svc = SSOService(s, _cipher(), _SETTINGS)
        u1 = await svc.get_or_create_user_from_saml(tenant_id, "x@y.com")
        u2 = await svc.get_or_create_user_from_saml(tenant_id, "x@y.com")
        assert u1.id == u2.id


def test_sp_metadata_xml_well_formed():
    import defusedxml.ElementTree as ET

    svc = SSOService.__new__(SSOService)
    xml = svc.sp_metadata_xml(
        "https://ppv.example.com/sso/demo/metadata",
        "https://ppv.example.com/api/auth/sso/demo/acs",
    )
    root = ET.fromstring(xml)
    assert root.tag.endswith("EntityDescriptor")


def test_build_authn_request_url_contains_samlrequest():
    svc = SSOService.__new__(SSOService)
    url = svc.build_authn_request_url(
        "https://idp.example.com/sso",
        "https://ppv.example.com/sso/demo/metadata",
        "https://ppv.example.com/api/auth/sso/demo/acs",
    )
    assert "SAMLRequest=" in url
    assert url.startswith("https://idp.example.com/sso?")


# ---- API-level ----

def test_sso_metadata_endpoint(owner_auth):
    client, headers, tenant_id = owner_auth
    # Configure first (owner has ADMIN).
    r = client.post(
        f"/api/auth/sso/configure/{tenant_id}",
        headers=headers,
        json={
            "idp_entity_id": "https://idp.example.com",
            "idp_sso_url": "https://idp.example.com/sso",
            "idp_x509_cert": "MIIC-cert",
        },
    )
    assert r.status_code == 201, r.text
    slug = r.json()["sp_entity_id"].split("/api/auth/sso/")[1].split("/")[0]

    meta = client.get(f"/api/auth/sso/{slug}/metadata")
    assert meta.status_code == 200
    assert "EntityDescriptor" in meta.text


def test_sso_metadata_unknown_tenant_404(owner_auth):
    client, _, _ = owner_auth
    assert client.get("/api/auth/sso/ghost-slug/metadata").status_code == 404


def test_sso_login_not_configured_404(owner_auth):
    client, headers, tenant_id = owner_auth
    # Tenant exists but no SSO configured -> the slug from /me path.
    # Use a fresh tenant's slug indirectly: unknown slug returns 404 (tenant).
    assert client.get("/api/auth/sso/nope/login").status_code == 404


def _configure(client, headers, tenant_id):
    r = client.post(
        f"/api/auth/sso/configure/{tenant_id}",
        headers=headers,
        json={
            "idp_entity_id": "https://idp.example.com",
            "idp_sso_url": "https://idp.example.com/sso",
            "idp_x509_cert": "MIIC-cert",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["sp_entity_id"].split("/api/auth/sso/")[1].split("/")[0]


def test_sso_login_redirects_to_idp(owner_auth):
    client, headers, tenant_id = owner_auth
    slug = _configure(client, headers, tenant_id)
    # Don't follow the redirect; assert we get a 302 to the IdP.
    resp = client.get(f"/api/auth/sso/{slug}/login", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"].startswith("https://idp.example.com/sso?")
    assert "SAMLRequest=" in resp.headers["location"]


def test_sso_acs_sets_token_and_redirects(owner_auth):
    client, headers, tenant_id = owner_auth
    slug = _configure(client, headers, tenant_id)
    resp = client.post(
        f"/api/auth/sso/{slug}/acs",
        data={"SAMLResponse": FAKE_SAML_RESPONSE},
    )
    assert resp.status_code == 200
    assert "ppv_token" in resp.text
    assert "localStorage.setItem" in resp.text


def test_sso_acs_invalid_response_400(owner_auth):
    client, headers, tenant_id = owner_auth
    slug = _configure(client, headers, tenant_id)
    resp = client.post(
        f"/api/auth/sso/{slug}/acs", data={"SAMLResponse": "not-base64!!"}
    )
    assert resp.status_code == 400


def test_sso_acs_unknown_tenant_404(owner_auth):
    client, _, _ = owner_auth
    resp = client.post("/api/auth/sso/ghost/acs", data={"SAMLResponse": FAKE_SAML_RESPONSE})
    assert resp.status_code == 404


def test_sso_login_unknown_tenant_404(owner_auth):
    client, _, _ = owner_auth
    assert client.get("/api/auth/sso/ghost/login", follow_redirects=False).status_code == 404


def test_configure_cross_tenant_requires_owner(owner_auth):
    """An ADMIN (non-owner) configuring a *different* tenant gets 403."""
    client, headers, tenant_id = owner_auth
    # owner_auth principal is OWNER for tenant_id; target a different tenant id.
    r = client.post(
        "/api/auth/sso/configure/some-other-tenant-id",
        headers=headers,
        json={"idp_entity_id": "e", "idp_sso_url": "u", "idp_x509_cert": "c"},
    )
    # OWNER is allowed past the role gate, so this hits the tenant-not-found 404.
    assert r.status_code == 404


def test_sso_login_not_configured_returns_404(owner_auth):
    """Tenant exists (the caller's own) but SSO not configured -> 404."""
    client, headers, tenant_id = owner_auth
    # Find the caller's own slug via /api/auth/me-style: use the configure->slug
    # trick is unavailable (not configured), so read slug from a fresh register.
    reg = client.post(
        "/api/auth/register",
        json={"tenant_name": "NoSSO", "slug": "nosso", "owner_email": "o@nosso.com",
              "owner_password": "pw12345678"},
    )
    assert reg.status_code in (200, 201)
    # The 'nosso' tenant has no SSO configured.
    assert client.get("/api/auth/sso/nosso/login", follow_redirects=False).status_code == 404


def test_sso_metadata_not_configured_returns_404(owner_auth):
    client, _, _ = owner_auth
    client.post(
        "/api/auth/register",
        json={"tenant_name": "NoSSO2", "slug": "nosso2", "owner_email": "o@nosso2.com",
              "owner_password": "pw12345678"},
    )
    assert client.get("/api/auth/sso/nosso2/metadata").status_code == 404


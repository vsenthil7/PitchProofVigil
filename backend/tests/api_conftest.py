"""Fixtures for the enterprise API tests."""
from __future__ import annotations

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.core.config import Settings
from app.db.engine import Database


@pytest.fixture
def api_settings():
    return Settings(
        database_dsn="sqlite+aiosqlite:///:memory:",
        jwt_secret="test-secret",
        use_mocks=True,
        # Don't do real DNS resolution for webhook URLs in API tests; the SSRF
        # guard's resolution path is covered directly in test_url_safety.py.
        webhook_resolve_dns=False,
    )


@pytest_asyncio.fixture
async def client(api_settings):
    """A TestClient with a fresh in-memory DB and lifespan run."""
    db = Database(api_settings)
    app = create_app(api_settings, database=db, create_schema=True)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def owner_auth(client):
    """Register a tenant and return (client, headers, tenant_id)."""
    r = client.post(
        "/api/auth/register",
        json={
            "tenant_name": "WC Ops",
            "slug": "wc-ops",
            "owner_email": "o@wc.com",
            "owner_password": "pw123456",
        },
    )
    tenant_id = r.json()["tenant_id"]
    tok = client.post(
        "/api/auth/login",
        json={"tenant_id": tenant_id, "email": "o@wc.com", "password": "pw123456"},
    ).json()["access_token"]
    return client, {"Authorization": f"Bearer {tok}"}, tenant_id

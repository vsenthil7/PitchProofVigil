"""Tests for the global error envelope, request-id, and pagination."""
from __future__ import annotations

import pytest
from fastapi import APIRouter

from app.pagination.page import PageParams


# ---- Error envelope + request id ----

def test_404_uses_error_envelope(owner_auth):
    client, headers, _ = owner_auth
    r = client.get("/api/traces/does-not-exist", headers=headers)
    assert r.status_code == 404
    body = r.json()
    assert "error" in body
    assert body["error"]["code"] == 404
    assert "request_id" in body["error"]
    # The request id is echoed in the header too.
    assert r.headers["X-Request-ID"] == body["error"]["request_id"]


def test_request_id_header_on_success(owner_auth):
    client, headers, _ = owner_auth
    r = client.get("/api/stats", headers=headers)
    assert "X-Request-ID" in r.headers


def test_validation_error_envelope(owner_auth):
    client, headers, _ = owner_auth
    r = client.post("/api/ask", headers=headers, json={"text": ""})
    assert r.status_code == 422
    body = r.json()
    assert body["error"]["code"] == 422
    assert "details" in body["error"]


def test_incoming_request_id_preserved(owner_auth):
    client, headers, _ = owner_auth
    r = client.get("/api/stats", headers={**headers, "X-Request-ID": "trace-abc-123"})
    assert r.headers["X-Request-ID"] == "trace-abc-123"


def test_unhandled_exception_returns_500_envelope(api_settings, monkeypatch):
    # TestClient re-raises server exceptions by default; disable that so the
    # installed 500 handler is exercised as it would be in production.
    from fastapi.testclient import TestClient

    from app.api.app import create_app
    from app.db.engine import Database
    import app.api.routers.evaluation as ev

    class Boom:
        def __init__(self, *a, **k):
            raise RuntimeError("kaboom internal detail")

    db = Database(api_settings)
    app = create_app(api_settings, database=db, create_schema=True)
    with TestClient(app, raise_server_exceptions=False) as client:
        reg = client.post(
            "/api/auth/register",
            json={"tenant_name": "T", "slug": "t", "owner_email": "o@t.com", "owner_password": "pw12345678"},
        )
        tid = reg.json()["tenant_id"]
        tok = client.post(
            "/api/auth/login",
            json={"tenant_id": tid, "email": "o@t.com", "password": "pw12345678"},
        ).json()["access_token"]
        monkeypatch.setattr(ev, "TraceRepository", Boom)
        r = client.get("/api/stats", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 500
        body = r.json()
        assert body["error"]["message"] == "Internal server error"
        assert "kaboom" not in r.text  # internal detail never leaked
        assert "X-Request-ID" in r.headers


# ---- Pagination wired into endpoints ----

def test_traces_paginated_envelope(owner_auth):
    client, headers, _ = owner_auth
    for i in range(3):
        client.post("/api/ask", headers=headers, json={"text": "I want to buy a ticket"})
    r = client.get("/api/traces?limit=2&offset=0", headers=headers).json()
    assert "items" in r and "page" in r
    assert len(r["items"]) == 2
    assert r["page"]["total"] == 3
    assert r["page"]["has_more"] is True
    assert r["page"]["next_offset"] == 2
    # Second page.
    r2 = client.get("/api/traces?limit=2&offset=2", headers=headers).json()
    assert len(r2["items"]) == 1
    assert r2["page"]["has_more"] is False


def test_limit_is_clamped(owner_auth):
    client, headers, _ = owner_auth
    client.post("/api/ask", headers=headers, json={"text": "I want to buy a ticket"})
    r = client.get("/api/traces?limit=99999", headers=headers).json()
    assert r["page"]["limit"] == 200  # MAX_LIMIT


def test_audit_paginated(owner_auth):
    client, headers, _ = owner_auth
    client.post("/api/ask", headers=headers, json={"text": "which gate do I use"})
    r = client.get("/api/audit?limit=10&offset=0", headers=headers).json()
    assert "items" in r and "page" in r
    assert r["page"]["total"] >= 1

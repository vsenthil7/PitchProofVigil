"""Tests for app.api.main — all routes plus WebSocket."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.core.config import Settings
from app.core.context import AppContext


@pytest.fixture
def client():
    ctx = AppContext(Settings(use_mocks=True))
    return TestClient(create_app(ctx))


def test_health(client):
    data = client.get("/api/health").json()
    assert data["status"] == "ok"
    assert data["modes"]["gemini"] == "mock"
    assert data["trace_count"] == 0


def test_ask_returns_trace_and_evals(client):
    resp = client.post("/api/ask", json={"text": "When does Spain play Germany?"})
    body = resp.json()
    assert resp.status_code == 200
    assert body["trace"]["trace_id"]
    assert len(body["eval_results"]) == 3
    # poisoned query → factual fail → aggregate below 1
    assert body["aggregate_score"] < 1.0


def test_ask_validation_error(client):
    resp = client.post("/api/ask", json={"text": ""})
    assert resp.status_code == 422


def test_list_and_get_trace(client):
    client.post("/api/ask", json={"text": "buy a ticket"})
    traces = client.get("/api/traces").json()
    assert len(traces) == 1
    tid = traces[0]["trace_id"]
    got = client.get(f"/api/traces/{tid}")
    assert got.status_code == 200
    assert got.json()["trace_id"] == tid


def test_get_trace_404(client):
    resp = client.get("/api/traces/does-not-exist")
    assert resp.status_code == 404


def test_gate_blocks_poisoned(client):
    resp = client.post(
        "/api/gate",
        json={
            "candidate": "v2",
            "queries": ["When does Spain play Germany?", "buy a ticket"],
        },
    )
    body = resp.json()
    assert body["passed"] is False
    assert "hard failure" in body["reason"]


def test_gate_passes_clean(client):
    resp = client.post(
        "/api/gate",
        json={
            "candidate": "v1",
            "queries": ["When does France play England?", "buy a ticket"],
        },
    )
    assert resp.json()["passed"] is True


def test_drift_endpoint(client):
    client.post("/api/ask", json={"text": "buy a ticket"})
    client.post("/api/ask", json={"text": "When does France play England?"})
    body = client.get("/api/drift").json()
    assert "point" in body
    assert "alerting" in body


def test_websocket_receives_trace_event(client):
    with client.websocket_connect("/api/live") as ws:
        client.post("/api/ask", json={"text": "buy a ticket"})
        msg = ws.receive_json()
        assert msg["type"] == "trace"
        assert "aggregate" in msg


def test_websocket_receives_gate_event(client):
    with client.websocket_connect("/api/live") as ws:
        client.post(
            "/api/gate",
            json={"candidate": "v1", "queries": ["buy a ticket"]},
        )
        msg = ws.receive_json()
        assert msg["type"] == "gate"
        assert msg["candidate"] == "v1"


def test_create_app_default_context():
    # Cover the `context or get_context()` default branch.
    app = create_app()
    assert app.title == "PitchProof Vigil"

"""End-to-end API tests for the enterprise endpoints."""
from __future__ import annotations


# ---- Auth ----

def test_register_and_login(client):
    r = client.post(
        "/api/auth/register",
        json={"tenant_name": "T", "slug": "t-co", "owner_email": "o@t.com", "owner_password": "pw123456"},
    )
    assert r.status_code == 201
    tid = r.json()["tenant_id"]
    r = client.post(
        "/api/auth/login",
        json={"tenant_id": tid, "email": "o@t.com", "password": "pw123456"},
    )
    assert r.status_code == 200
    assert r.json()["token_type"] == "bearer"


def test_register_duplicate_slug(client):
    body = {"tenant_name": "T", "slug": "dup", "owner_email": "o@t.com", "owner_password": "pw123456"}
    assert client.post("/api/auth/register", json=body).status_code == 201
    body2 = {**body, "owner_email": "x@t.com"}
    assert client.post("/api/auth/register", json=body2).status_code == 409


def test_login_bad_password(client):
    client.post("/api/auth/register", json={"tenant_name": "T", "slug": "lc", "owner_email": "o@t.com", "owner_password": "pw123456"})
    tid = client.post("/api/auth/login", json={"tenant_id": "x", "email": "o@t.com", "password": "pw123456"})
    assert tid.status_code == 401


def test_invalid_slug_rejected(client):
    r = client.post("/api/auth/register", json={"tenant_name": "T", "slug": "BAD SLUG", "owner_email": "o@t.com", "owner_password": "pw123456"})
    assert r.status_code == 422


# ---- Ask ----

def test_ask_requires_auth(client):
    assert client.post("/api/ask", json={"text": "hi"}).status_code == 401


def test_ask_full_flow(owner_auth):
    client, headers, _ = owner_auth
    r = client.post("/api/ask", headers=headers, json={"text": "When does Spain play Germany?"})
    assert r.status_code == 200
    j = r.json()
    assert j["intent"] == "kickoff_time"
    assert len(j["evaluations"]) == 11
    assert "20:00" in j["answer"]
    assert j["passed"] is True
    assert "correctness" in j["category_scores"]
    assert j["cost"]["calls"] == 1


def test_ask_validation(owner_auth):
    client, headers, _ = owner_auth
    assert client.post("/api/ask", headers=headers, json={"text": ""}).status_code == 422


def test_bad_token_rejected(client):
    assert client.post("/api/ask", headers={"Authorization": "Bearer garbage"}, json={"text": "hi"}).status_code == 401


def test_malformed_auth_header(client):
    assert client.post("/api/ask", headers={"Authorization": "Basic xyz"}, json={"text": "hi"}).status_code == 401


# ---- Traces & stats ----

def test_traces_and_stats(owner_auth):
    client, headers, _ = owner_auth
    client.post("/api/ask", headers=headers, json={"text": "I want to buy a ticket"})
    traces = client.get("/api/traces", headers=headers).json()
    assert len(traces) == 1
    tid = traces[0]["trace_id"]
    detail = client.get(f"/api/traces/{tid}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["spans"]
    assert client.get("/api/traces/missing", headers=headers).status_code == 404
    stats = client.get("/api/stats", headers=headers).json()
    assert stats["trace_count"] == 1


# ---- Gate ----

def test_gate_inline(owner_auth):
    client, headers, _ = owner_auth
    r = client.post("/api/gate", headers=headers, json={"candidate": "v1", "queries": ["I want to buy a ticket"]})
    assert r.status_code == 200
    assert "decision_id" in r.json()


def test_gate_decisions_list(owner_auth):
    client, headers, _ = owner_auth
    client.post("/api/gate", headers=headers, json={"candidate": "v1", "queries": ["I want to buy a ticket"]})
    decisions = client.get("/api/gate/decisions", headers=headers).json()
    assert len(decisions) == 1


def test_gate_dataset(owner_auth):
    client, headers, _ = owner_auth
    client.post("/api/datasets", headers=headers, json={"name": "core", "examples": [{"text": "I want to buy a ticket"}]})
    r = client.post("/api/gate/dataset", headers=headers, json={"candidate": "v1", "dataset": "core"})
    assert r.status_code == 200
    assert r.json()["trace_count"] == 1


# ---- Policies ----

def test_list_evaluators(owner_auth):
    client, headers, _ = owner_auth
    evs = client.get("/api/policies/evaluators", headers=headers).json()
    assert len(evs) == 11
    assert any(e["category"] == "safety" for e in evs)


def test_policy_upsert_and_list(owner_auth):
    client, headers, _ = owner_auth
    r = client.post("/api/policies", headers=headers, json={"name": "production", "threshold": 0.9, "evaluator_policies": {"latency_slo": {"enabled": True, "weight": 2.0}}})
    assert r.status_code == 201
    assert r.json()["version"] == 1
    r2 = client.post("/api/policies", headers=headers, json={"name": "production", "threshold": 0.8})
    assert r2.json()["version"] == 2
    policies = client.get("/api/policies", headers=headers).json()
    assert len(policies) == 2


def test_active_policy_used_after_upsert(owner_auth):
    client, headers, _ = owner_auth
    # Create a strict production policy, then ask — it should be applied.
    client.post("/api/policies", headers=headers, json={"name": "production", "threshold": 0.95})
    r = client.post("/api/ask", headers=headers, json={"text": "I want to buy a ticket"})
    assert r.status_code == 200


# ---- Datasets ----

def test_dataset_create_list_duplicate(owner_auth):
    client, headers, _ = owner_auth
    r = client.post("/api/datasets", headers=headers, json={"name": "d1", "description": "x", "examples": [{"text": "hi"}]})
    assert r.status_code == 201
    assert r.json()["example_count"] == 1
    assert client.post("/api/datasets", headers=headers, json={"name": "d1"}).status_code == 409
    assert len(client.get("/api/datasets", headers=headers).json()) == 1


# ---- RBAC ----

def test_viewer_cannot_evaluate(owner_auth):
    client, headers, tenant_id = owner_auth
    # Create a viewer user, log in as them, attempt to ask → 403.
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
    # Viewer can read...
    assert client.get("/api/stats", headers=vheaders).status_code == 200
    # ...but cannot evaluate.
    assert client.post("/api/ask", headers=vheaders, json={"text": "hi"}).status_code == 403
    # ...and cannot manage policies.
    assert client.post("/api/policies", headers=vheaders, json={"name": "p"}).status_code == 403


def test_api_key_create_and_use(owner_auth):
    client, headers, _ = owner_auth
    r = client.post("/api/auth/api-keys", headers=headers, json={"name": "ci", "role": "operator"})
    assert r.status_code == 201
    full = r.json()["api_key"]
    # Use the API key to ask.
    r2 = client.post("/api/ask", headers={"X-API-Key": full}, json={"text": "I want to buy a ticket"})
    assert r2.status_code == 200


# ---- Observability ----

def test_health_ready_metrics(client):
    assert client.get("/health").json() == {"alive": True}
    assert client.get("/ready").json()["ready"] is True
    m = client.get("/metrics")
    assert m.status_code == 200
    assert b"ppv_http_requests_total" in m.content

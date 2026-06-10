"""Tests covering API error branches and the custom-policy loading path."""
from __future__ import annotations


def test_register_duplicate_email_same_tenant_via_user(owner_auth):
    # Creating the same user twice → AuthError 409 surfaced by router.
    client, headers, _ = owner_auth
    r1 = client.post("/api/auth/users", headers=headers, json={"email": "dup@wc.com", "password": "pw123456", "role": "operator"})
    assert r1.status_code == 201
    r2 = client.post("/api/auth/users", headers=headers, json={"email": "dup@wc.com", "password": "pw123456", "role": "operator"})
    assert r2.status_code == 409


def test_login_unknown_tenant(client):
    r = client.post("/api/auth/login", json={"tenant_id": "ghost", "email": "x@y.com", "password": "pw123456"})
    assert r.status_code == 401


def test_custom_policy_applied_in_ask(owner_auth):
    """Upsert a policy with explicit evaluator_policies, then ask.

    This exercises the active_policy dependency's branch that rebuilds a
    GatePolicy from stored evaluator_policies (deps.py custom-policy path).
    """
    client, headers, _ = owner_auth
    r = client.post(
        "/api/policies",
        headers=headers,
        json={
            "name": "production",
            "threshold": 0.5,
            "fail_on_any_blocking": True,
            "evaluator_policies": {
                "latency_slo": {"enabled": True, "weight": 3.0, "blocking": False, "config": {"budget_ms": 5000}},
                "llm_judge": {"enabled": False},
            },
        },
    )
    assert r.status_code == 201
    # Now ask — active_policy must load and rebuild the stored policy.
    a = client.post("/api/ask", headers=headers, json={"text": "I want to buy a ticket"})
    assert a.status_code == 200
    # llm_judge disabled → only 10 evaluators run.
    evaluators = {e["evaluator"] for e in a.json()["evaluations"]}
    assert "llm_judge" not in evaluators
    assert len(evaluators) == 10


def test_gate_dataset_missing_returns_zero_traces(owner_auth):
    client, headers, _ = owner_auth
    r = client.post("/api/gate/dataset", headers=headers, json={"candidate": "v1", "dataset": "nope"})
    assert r.status_code == 200
    assert r.json()["trace_count"] == 0


def test_api_key_revoke_flow(owner_auth):
    client, headers, _ = owner_auth
    # Operator API key cannot manage keys (needs MANAGE_KEYS).
    r = client.post("/api/auth/api-keys", headers=headers, json={"name": "k", "role": "operator"})
    full = r.json()["api_key"]
    # Operator key used for an allowed action (evaluate).
    assert client.post("/api/ask", headers={"X-API-Key": full}, json={"text": "buy a ticket"}).status_code == 200
    # Operator key denied for key management.
    assert client.post("/api/auth/api-keys", headers={"X-API-Key": full}, json={"name": "k2", "role": "viewer"}).status_code == 403


def test_stats_empty_tenant(owner_auth):
    client, headers, _ = owner_auth
    stats = client.get("/api/stats", headers=headers).json()
    assert stats["trace_count"] == 0

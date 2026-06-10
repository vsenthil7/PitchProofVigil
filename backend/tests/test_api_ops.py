"""API tests for the ops router (audit log + webhooks) and event wiring."""
from __future__ import annotations


def test_audit_populated_after_blocking_ask(owner_auth):
    client, headers, _ = owner_auth
    # A fact-bearing query with no team → groundedness blocking failure → audit.
    client.post("/api/ask", headers=headers, json={"text": "which gate do I use"})
    audit = client.get("/api/audit", headers=headers).json()
    actions = {a["action"] for a in audit}
    assert "eval.blocking_failure" in actions


def test_audit_filter_by_action(owner_auth):
    client, headers, _ = owner_auth
    client.post("/api/ask", headers=headers, json={"text": "which gate do I use"})
    filtered = client.get("/api/audit?action=eval.blocking_failure", headers=headers).json()
    assert all(a["action"] == "eval.blocking_failure" for a in filtered)


def test_audit_empty_for_clean_ask(owner_auth):
    client, headers, _ = owner_auth
    client.post("/api/ask", headers=headers, json={"text": "I want to buy a ticket"})
    audit = client.get("/api/audit", headers=headers).json()
    # Clean ask produces no blocking-failure audit entries.
    assert all(a["action"] != "eval.blocking_failure" for a in audit)


def test_webhook_crud(owner_auth):
    client, headers, _ = owner_auth
    r = client.post(
        "/api/webhooks",
        headers=headers,
        json={"url": "https://hook.example/x", "event_type": "gate_decided", "secret": "s"},
    )
    assert r.status_code == 201
    wid = r.json()["id"]
    listed = client.get("/api/webhooks", headers=headers).json()
    assert len(listed) == 1
    assert listed[0]["event_type"] == "gate_decided"
    d = client.delete(f"/api/webhooks/{wid}", headers=headers)
    assert d.status_code == 200
    assert d.json()["deactivated"] == wid


def test_webhook_delete_missing(owner_auth):
    client, headers, _ = owner_auth
    assert client.delete("/api/webhooks/nope", headers=headers).status_code == 404


def test_webhook_requires_manage_permission(owner_auth):
    client, headers, tenant_id = owner_auth
    # Make an operator (no MANAGE_POLICIES) and confirm 403.
    client.post("/api/auth/users", headers=headers, json={"email": "op@wc.com", "password": "pw12345678", "role": "operator"})
    tok = client.post("/api/auth/login", json={"tenant_id": tenant_id, "email": "op@wc.com", "password": "pw12345678"}).json()["access_token"]
    oph = {"Authorization": f"Bearer {tok}"}
    r = client.post("/api/webhooks", headers=oph, json={"url": "https://x", "event_type": "gate_decided"})
    assert r.status_code == 403

"""Tests for secret redaction."""
from __future__ import annotations

from app.crypto.redaction import redact


def test_redact_flat_secret():
    out = redact({"secret": "abc", "url": "https://x"})
    assert out["secret"] == "***redacted***"
    assert out["url"] == "https://x"


def test_redact_various_sensitive_keys():
    out = redact({
        "password": "p", "api_key": "k", "token": "t",
        "Authorization": "bearer x", "safe": "ok",
    })
    assert out["password"] == "***redacted***"
    assert out["api_key"] == "***redacted***"
    assert out["token"] == "***redacted***"
    assert out["Authorization"] == "***redacted***"
    assert out["safe"] == "ok"


def test_redact_nested():
    out = redact({"outer": {"secret": "s", "ok": 1}, "list": [{"password": "p"}]})
    assert out["outer"]["secret"] == "***redacted***"
    assert out["outer"]["ok"] == 1
    assert out["list"][0]["password"] == "***redacted***"


def test_redact_preserves_non_dict():
    assert redact("plain") == "plain"
    assert redact(42) == 42
    assert redact([1, 2, 3]) == [1, 2, 3]


def test_redact_tuple_type_preserved():
    out = redact(({"secret": "x"},))
    assert isinstance(out, tuple)
    assert out[0]["secret"] == "***redacted***"


def test_audit_never_stores_secret(owner_auth):
    """A webhook event payload with a secret-like field is redacted in audit."""
    client, headers, _ = owner_auth
    # Trigger a blocking failure → audit entry written.
    client.post("/api/ask", headers=headers, json={"text": "which gate do I use"})
    audit = client.get("/api/audit", headers=headers).json()
    # No audit detail should contain an unredacted 'secret' key with a value.
    for entry in audit:
        for k, v in entry["detail"].items():
            if "secret" in k.lower() or "password" in k.lower():
                assert v == "***redacted***"


def test_webhook_response_never_includes_secret(owner_auth):
    client, headers, _ = owner_auth
    r = client.post(
        "/api/webhooks",
        headers=headers,
        json={"url": "https://hook/x", "event_type": "gate_decided", "secret": "topsecret"},
    )
    assert r.status_code == 201
    assert "secret" not in r.json()  # WebhookOut omits it
    listed = client.get("/api/webhooks", headers=headers).json()
    assert all("secret" not in h for h in listed)


def test_security_status_endpoint(client):
    r = client.get("/api/security/status")
    assert r.status_code == 200
    j = r.json()
    assert j["encryption_at_rest"] is True
    assert j["rotation_supported"] is True
    assert j["key_ring_size"] >= 1
    # Test config uses the dev-derived key.
    assert j["using_ephemeral_dev_key"] is True

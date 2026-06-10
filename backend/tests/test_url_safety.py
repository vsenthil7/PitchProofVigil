"""Tests for the webhook SSRF / URL-safety guard."""
from __future__ import annotations

import pytest

from app.webhooks.url_safety import UnsafeWebhookURL, validate_webhook_url


@pytest.mark.parametrize("url", [
    "https://hooks.example.com/path",
    "https://8.8.8.8/x",
])
def test_safe_urls_allowed(url):
    assert validate_webhook_url(url, resolve=False) == url


@pytest.mark.parametrize("url", [
    "https://localhost/x",
    "https://127.0.0.1/x",
    "https://10.0.0.5/x",
    "https://192.168.1.1/x",
    "https://169.254.169.254/latest/meta-data",
    "https://metadata.google.internal/x",
    "https://[::1]/x",
])
def test_unsafe_urls_blocked(url):
    with pytest.raises(UnsafeWebhookURL):
        validate_webhook_url(url, resolve=False)


def test_http_blocked_by_default():
    with pytest.raises(UnsafeWebhookURL):
        validate_webhook_url("http://hooks.example.com/x", resolve=False)


def test_http_allowed_when_enabled():
    assert validate_webhook_url("http://hooks.example.com/x", allow_http=True, resolve=False)


def test_bad_scheme_blocked():
    with pytest.raises(UnsafeWebhookURL):
        validate_webhook_url("ftp://example.com", resolve=False)


def test_no_host_blocked():
    with pytest.raises(UnsafeWebhookURL):
        validate_webhook_url("https:///nopath", resolve=False)


def test_unresolvable_host_blocked():
    with pytest.raises(UnsafeWebhookURL):
        validate_webhook_url("https://nonexistent.invalid.tld.example/x", resolve=True)


def test_public_host_resolves_ok(monkeypatch):
    import app.webhooks.url_safety as mod

    monkeypatch.setattr(mod.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 0))])
    assert validate_webhook_url("https://example.com/x", resolve=True)


def test_is_private_ip_handles_malformed():
    # Defensive branch: a non-IP string is treated as "not private" (the caller
    # never reaches the private check for such inputs, but the guard is safe).
    from app.webhooks.url_safety import _is_private_ip

    assert _is_private_ip("not-an-ip") is False


def test_dns_rebinding_private_resolution_blocked(monkeypatch):
    import app.webhooks.url_safety as mod

    # Host resolves to a private IP → blocked even though the name looks public.
    monkeypatch.setattr(mod.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("10.1.2.3", 0))])
    with pytest.raises(UnsafeWebhookURL):
        validate_webhook_url("https://sneaky.example.com/x", resolve=True)


# ---- Through the API ----

def test_create_webhook_rejects_internal_url(owner_auth):
    client, headers, _ = owner_auth
    r = client.post(
        "/api/webhooks",
        headers=headers,
        json={"url": "https://169.254.169.254/meta", "event_type": "gate_decided"},
    )
    assert r.status_code == 422
    assert "Unsafe webhook URL" in r.json()["error"]["message"]

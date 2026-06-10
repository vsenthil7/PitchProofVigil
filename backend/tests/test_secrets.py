"""Tests for the SecretProvider abstraction (C2)."""
from __future__ import annotations

from app.core.secrets import (
    EnvSecretProvider,
    GCPSecretProvider,
    get_secret_provider,
)


def test_env_secret_provider_reads_env(monkeypatch):
    monkeypatch.setenv("MY_SECRET", "shhh")
    assert EnvSecretProvider().get("MY_SECRET") == "shhh"


def test_env_secret_provider_missing_returns_none(monkeypatch):
    monkeypatch.delenv("NOPE_SECRET", raising=False)
    assert EnvSecretProvider().get("NOPE_SECRET") is None


def test_get_secret_provider_defaults_to_env():
    assert isinstance(get_secret_provider(), EnvSecretProvider)


def test_get_secret_provider_with_project_returns_gcp():
    provider = get_secret_provider("my-project")
    assert isinstance(provider, GCPSecretProvider)


def test_gcp_provider_falls_back_to_env_when_sdk_missing(monkeypatch):
    """When the GCP SDK isn't installed, the client is None and env is used."""
    monkeypatch.setenv("FALLBACK_SECRET", "from-env")
    provider = GCPSecretProvider("my-project")
    # In the sandbox the google-cloud-secret-manager SDK is absent -> client None.
    assert provider._client is None
    assert provider.get("FALLBACK_SECRET") == "from-env"

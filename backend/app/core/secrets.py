"""SecretProvider abstraction.

Supports environment variables (default, always available) and GCP Secret
Manager when a project is configured and ``google-cloud-secret-manager`` is
installed. The GCP provider falls back to env vars if the SDK is missing or a
lookup fails, so laptop/dev use is never broken.
"""
from __future__ import annotations

import os
from typing import Protocol


class SecretProvider(Protocol):
    def get(self, name: str) -> str | None: ...


class EnvSecretProvider:
    """Reads secrets from environment variables."""

    def get(self, name: str) -> str | None:
        return os.getenv(name)


class GCPSecretProvider:
    """Reads secrets from GCP Secret Manager, falling back to env vars."""

    def __init__(self, project: str) -> None:
        self._project = project
        self._fallback = EnvSecretProvider()
        try:  # pragma: no cover - requires optional google-cloud-secret-manager
            from google.cloud import secretmanager

            self._client = secretmanager.SecretManagerServiceClient()
        except ImportError:
            self._client = None

    def get(self, name: str) -> str | None:
        if self._client is None:
            return self._fallback.get(name)
        try:  # pragma: no cover - requires live GCP Secret Manager
            path = f"projects/{self._project}/secrets/{name}/versions/latest"
            response = self._client.access_secret_version(name=path)
            return response.payload.data.decode("utf-8")
        except Exception:  # pragma: no cover - requires live GCP Secret Manager
            return self._fallback.get(name)


def get_secret_provider(project: str | None = None) -> SecretProvider:
    if project:
        return GCPSecretProvider(project)
    return EnvSecretProvider()

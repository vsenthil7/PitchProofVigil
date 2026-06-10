"""Encryption key provider.

Keys come from the environment as a comma-separated list of urlsafe-base64
Fernet keys (newest first). MultiFernet encrypts with the first and can decrypt
with any, which is exactly what zero-downtime key rotation needs: prepend a new
key, redeploy, re-encrypt lazily, then drop the old key later.

If no key is configured we derive a deterministic *development* key from the
JWT secret so local/test runs work without extra setup — never do this in prod,
and the provider says so via ``is_ephemeral``.
"""
from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, MultiFernet

from app.core.config import Settings


def _derive_dev_key(seed: str) -> str:
    digest = hashlib.sha256(seed.encode()).digest()
    return base64.urlsafe_b64encode(digest).decode()


class KeyProvider:
    """Supplies a MultiFernet built from the configured key ring."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        raw = (settings.encryption_keys or "").strip()
        if raw:
            self._keys = [k.strip() for k in raw.split(",") if k.strip()]
            self.is_ephemeral = False
        else:
            # Deterministic dev key derived from the JWT secret.
            self._keys = [_derive_dev_key(settings.jwt_secret)]
            self.is_ephemeral = True

    @property
    def key_count(self) -> int:
        return len(self._keys)

    def multifernet(self) -> MultiFernet:
        return MultiFernet([Fernet(k) for k in self._keys])

    @staticmethod
    def generate_key() -> str:
        """Generate a fresh Fernet key (for ops to add to the ring)."""
        return Fernet.generate_key().decode()

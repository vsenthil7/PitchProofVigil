"""Field-level encryption helper.

Wraps a KeyProvider's MultiFernet with a versioned, prefixed ciphertext format
so encrypted values are self-describing and safe to store as text. Plaintext
passed to ``decrypt`` that lacks the prefix is returned unchanged — this makes
migration from plaintext columns seamless (decrypt tolerates legacy rows).
"""
from __future__ import annotations

from cryptography.fernet import InvalidToken

from app.crypto.keys import KeyProvider

_PREFIX = "enc:v1:"


class FieldCipher:
    def __init__(self, provider: KeyProvider) -> None:
        self._fernet = provider.multifernet()

    def encrypt(self, plaintext: str) -> str:
        if plaintext == "":
            return ""
        token = self._fernet.encrypt(plaintext.encode()).decode()
        return f"{_PREFIX}{token}"

    def decrypt(self, value: str) -> str:
        if value == "":
            return ""
        if not value.startswith(_PREFIX):
            # Legacy plaintext (pre-encryption rows) — return as-is.
            return value
        token = value[len(_PREFIX):]
        try:
            return self._fernet.decrypt(token.encode()).decode()
        except InvalidToken as exc:
            raise ValueError("Unable to decrypt value (wrong or rotated-out key)") from exc

    def is_encrypted(self, value: str) -> bool:
        return value.startswith(_PREFIX)

    def rotate(self, value: str) -> str:
        """Re-encrypt a value under the current primary key."""
        return self.encrypt(self.decrypt(value))

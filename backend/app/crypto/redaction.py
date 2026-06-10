"""Secret redaction helpers.

Used to scrub sensitive values from structured log payloads and any dict that
might be serialized. Matches keys by name (case-insensitive substring) so
'secret', 'password', 'api_key', 'token', 'authorization' are masked wherever
they appear, including nested dicts/lists.
"""
from __future__ import annotations

from typing import Any

_SENSITIVE = ("secret", "password", "passwd", "api_key", "apikey", "token", "authorization")
_MASK = "***redacted***"


def _is_sensitive(key: str) -> bool:
    k = key.lower()
    return any(s in k for s in _SENSITIVE)


def redact(value: Any) -> Any:
    """Return a copy of ``value`` with sensitive fields masked, recursively."""
    if isinstance(value, dict):
        return {
            k: (_MASK if _is_sensitive(str(k)) else redact(v)) for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return type(value)(redact(v) for v in value)
    return value

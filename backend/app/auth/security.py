"""Security primitives: password hashing, API-key minting, and JWT.

Passwords use bcrypt via passlib. API keys are shown once at creation as
``{prefix}_{secret}``; only a hash of the secret is stored, and lookups are by
the public prefix. JWTs are signed with the configured secret/algorithm.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import Settings, get_settings

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


# --- Passwords -----------------------------------------------------------


def hash_password(password: str) -> str:
    return _pwd.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _pwd.verify(password, hashed)
    except ValueError:
        return False


# --- API keys ------------------------------------------------------------


def _hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def mint_api_key(settings: Settings | None = None) -> tuple[str, str, str]:
    """Return (full_key, prefix, hashed_secret).

    The full key is shown to the user exactly once. We store only prefix +
    hashed secret. Prefix is random so it is safe to index and expose.
    """
    settings = settings or get_settings()
    prefix = f"{settings.api_key_prefix}_{secrets.token_hex(4)}"
    secret = secrets.token_urlsafe(32)
    full = f"{prefix}.{secret}"
    return full, prefix, _hash_secret(secret)


def split_api_key(full_key: str) -> tuple[str, str] | None:
    """Split a presented key into (prefix, secret); None if malformed."""
    if "." not in full_key:
        return None
    prefix, _, secret = full_key.partition(".")
    if not prefix or not secret:
        return None
    return prefix, secret


def verify_api_secret(secret: str, hashed_secret: str) -> bool:
    return secrets.compare_digest(_hash_secret(secret), hashed_secret)


# --- JWT -----------------------------------------------------------------


def create_access_token(
    subject: str,
    tenant_id: str,
    role: str,
    settings: Settings | None = None,
    expires_minutes: int | None = None,
) -> str:
    settings = settings or get_settings()
    ttl = expires_minutes or settings.access_token_ttl_minutes
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "tenant_id": tenant_id,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=ttl)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str, settings: Settings | None = None) -> dict | None:
    settings = settings or get_settings()
    try:
        return jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except JWTError:
        return None

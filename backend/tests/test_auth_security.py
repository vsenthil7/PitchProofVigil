"""Tests for auth security primitives."""
from __future__ import annotations

from app.auth.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    mint_api_key,
    split_api_key,
    verify_api_secret,
    verify_password,
)
from app.core.config import Settings


def test_password_hash_roundtrip():
    h = hash_password("s3cret-pw")
    assert h != "s3cret-pw"
    assert verify_password("s3cret-pw", h)
    assert not verify_password("wrong", h)


def test_verify_password_handles_bad_hash():
    assert verify_password("x", "not-a-real-hash") is False


def test_mint_and_verify_api_key():
    settings = Settings(api_key_prefix="ppv")
    full, prefix, hashed = mint_api_key(settings)
    assert full.startswith("ppv_")
    assert prefix.startswith("ppv_")
    parts = split_api_key(full)
    assert parts is not None
    p, secret = parts
    assert p == prefix
    assert verify_api_secret(secret, hashed)
    assert not verify_api_secret("wrong", hashed)


def test_split_api_key_malformed():
    assert split_api_key("no-dot") is None
    assert split_api_key(".secret") is None
    assert split_api_key("prefix.") is None


def test_jwt_roundtrip():
    settings = Settings(jwt_secret="unit-secret")
    token = create_access_token("user1", "tenant1", "admin", settings)
    claims = decode_access_token(token, settings)
    assert claims["sub"] == "user1"
    assert claims["tenant_id"] == "tenant1"
    assert claims["role"] == "admin"


def test_jwt_invalid_returns_none():
    settings = Settings(jwt_secret="unit-secret")
    assert decode_access_token("garbage.token.here", settings) is None


def test_jwt_wrong_secret_rejected():
    s1 = Settings(jwt_secret="secret-a")
    s2 = Settings(jwt_secret="secret-b")
    token = create_access_token("u", "t", "viewer", s1)
    assert decode_access_token(token, s2) is None


def test_jwt_custom_expiry():
    settings = Settings(jwt_secret="s")
    token = create_access_token("u", "t", "owner", settings, expires_minutes=5)
    assert decode_access_token(token, settings) is not None

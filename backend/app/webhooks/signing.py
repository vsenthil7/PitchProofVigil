"""Webhook payload signing.

Each subscription has a secret; deliveries are signed with HMAC-SHA256 over the
raw JSON body plus a timestamp, so receivers can verify authenticity and reject
replays. Mirrors the Stripe-style ``t=...,v1=...`` signature header.
"""
from __future__ import annotations

import hashlib
import hmac
import time


def sign_payload(secret: str, body: bytes, timestamp: int | None = None) -> str:
    """Return a signature header value: ``t=<ts>,v1=<hexdigest>``."""
    ts = int(time.time()) if timestamp is None else timestamp
    signed = f"{ts}.".encode() + body
    digest = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return f"t={ts},v1={digest}"


def verify_signature(secret: str, body: bytes, header: str, tolerance_s: int = 300) -> bool:
    """Verify a signature header produced by ``sign_payload``."""
    parts = dict(p.split("=", 1) for p in header.split(",") if "=" in p)
    ts_raw, sig = parts.get("t"), parts.get("v1")
    if ts_raw is None or sig is None:
        return False
    try:
        ts = int(ts_raw)
    except ValueError:
        return False
    if abs(int(time.time()) - ts) > tolerance_s:
        return False
    expected = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)

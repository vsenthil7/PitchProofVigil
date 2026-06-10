"""Test that the rate-limit middleware returns 429 when the bucket is empty."""
from __future__ import annotations

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.core.config import Settings
from app.db.engine import Database


@pytest.fixture
def tiny_limit_client():
    # Capacity 3, no refill → 4th authenticated /api call is rejected.
    settings = Settings(
        database_dsn="sqlite+aiosqlite:///:memory:",
        jwt_secret="test-secret",
        use_mocks=True,
        rate_limit_capacity=3,
        rate_limit_refill_per_second=0,
    )
    db = Database(settings)
    app = create_app(settings, database=db, create_schema=True)
    with TestClient(app) as c:
        yield c


def test_rate_limit_returns_429(tiny_limit_client):
    c = tiny_limit_client
    reg = c.post(
        "/api/auth/register",
        json={"tenant_name": "T", "slug": "t", "owner_email": "o@t.com", "owner_password": "pw12345678"},
    )
    tid = reg.json()["tenant_id"]
    tok = c.post(
        "/api/auth/login",
        json={"tenant_id": tid, "email": "o@t.com", "password": "pw12345678"},
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    # register + login already consumed tokens against this auth key? No — the
    # bucket key is the Authorization header, which only exists post-login.
    # Burn the remaining tokens then expect a 429.
    statuses = [c.get("/api/stats", headers=h).status_code for _ in range(6)]
    assert 429 in statuses
    # Health endpoint is exempt (no /api/ prefix on the limiter key path check).
    assert c.get("/health").status_code == 200


def test_unauthenticated_not_rate_limited(tiny_limit_client):
    c = tiny_limit_client
    # No auth header → limiter is bypassed; many calls all 401, never 429.
    statuses = [c.post("/api/ask", json={"text": "x"}).status_code for _ in range(10)]
    assert all(s == 401 for s in statuses)


def test_async_redis_limiter_middleware_branch():
    """The middleware awaits an async (Redis) limiter and returns 429 when denied.

    Exercises the asyncio.iscoroutinefunction(limiter.check) branch with a
    real RedisRateLimiter over fakeredis (capacity 2, no refill).
    """
    import fakeredis.aioredis as fakeredis

    from app.ratelimit.redis_bucket import RedisRateLimiter

    settings = Settings(
        database_dsn="sqlite+aiosqlite:///:memory:",
        jwt_secret="test-secret",
        use_mocks=True,
    )
    db = Database(settings)
    app = create_app(settings, database=db, create_schema=True)
    with TestClient(app) as c:
        # Swap in an async distributed limiter after startup.
        app.state.rate_limiter = RedisRateLimiter(
            redis_client=fakeredis.FakeRedis(),
            capacity=2.0,
            refill_per_second=0.0,
        )
        reg = c.post(
            "/api/auth/register",
            json={"tenant_name": "R", "slug": "r", "owner_email": "o@r.com", "owner_password": "pw12345678"},
        )
        tid = reg.json()["tenant_id"]
        tok = c.post(
            "/api/auth/login",
            json={"tenant_id": tid, "email": "o@r.com", "password": "pw12345678"},
        ).json()["access_token"]
        h = {"Authorization": f"Bearer {tok}"}
        statuses = [c.get("/api/stats", headers=h).status_code for _ in range(5)]
        assert 429 in statuses

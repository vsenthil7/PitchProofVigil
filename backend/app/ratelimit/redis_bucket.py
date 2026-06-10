"""Redis-backed distributed rate limiter.

Uses a Lua script executed atomically via EVALSHA to implement a sliding-window
token bucket. This ensures correctness across multiple Uvicorn workers or Cloud
Run replicas sharing the same Redis instance.

The interface mirrors the in-process ``RateLimiter`` (``check`` / ``remaining``)
so the middleware can swap implementations without code change. ``check`` here
is async (Redis I/O); the middleware detects this and awaits accordingly.

Fallback: if REDIS_URL is absent or Redis is unreachable, the app keeps the
in-process ``RateLimiter``; and even when wired, ``check`` fails open (returns
True) on any Redis error so a Redis blip never takes the API down.
"""
from __future__ import annotations

import time

# Sliding-window token bucket, executed atomically inside Redis.
#   KEYS[1] = rate-limit key (e.g. "rl:Bearer eyJ...")
#   ARGV[1] = capacity (max tokens)
#   ARGV[2] = refill_per_second
#   ARGV[3] = current timestamp (float seconds)
#   ARGV[4] = cost (tokens to consume, usually 1.0)
# Returns 1 if allowed, 0 if denied.
_LUA_SCRIPT = """
local key = KEYS[1]
local cap = tonumber(ARGV[1])
local refill = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local cost = tonumber(ARGV[4])
local state = redis.call('HMGET', key, 'tokens', 'last')
local tokens = tonumber(state[1]) or cap
local last = tonumber(state[2]) or now
local elapsed = math.max(0, now - last)
tokens = math.min(cap, tokens + elapsed * refill)
if tokens >= cost then
    tokens = tokens - cost
    redis.call('HMSET', key, 'tokens', tokens, 'last', now)
    redis.call('EXPIRE', key, 3600)
    return 1
end
redis.call('HMSET', key, 'tokens', tokens, 'last', now)
redis.call('EXPIRE', key, 3600)
return 0
"""


def _is_scripting_unsupported(exc: Exception) -> bool:
    """True if the error indicates the server lacks Lua scripting (e.g.
    fakeredis: 'unknown command SCRIPT/EVALSHA'). Such errors mean we should
    fall back to the non-atomic path rather than fail open."""
    msg = str(exc).lower()
    return "unknown command" in msg and ("script" in msg or "evalsha" in msg)


class RedisRateLimiter:
    """Distributed token bucket backed by Redis EVALSHA.

    Drop-in async replacement for ``RateLimiter``: ``check`` and ``remaining``
    keep the same call signatures (but are coroutines).
    """

    def __init__(
        self,
        redis_client,
        capacity: float = 120.0,
        refill_per_second: float = 10.0,
    ) -> None:
        self._redis = redis_client
        self.capacity = capacity
        self.refill = refill_per_second
        self._sha: str | None = None

    async def _ensure_sha(self) -> str:
        """Load the Lua script once and cache its SHA."""
        if self._sha is None:
            self._sha = await self._redis.script_load(_LUA_SCRIPT)
        return self._sha

    async def _consume_lua(self, key: str, tokens: float) -> bool | None:
        """Atomic path via Lua. Returns the decision, or None if the server
        doesn't support scripting (e.g. fakeredis), so the caller can fall back.
        """
        try:
            sha = await self._ensure_sha()
            result = await self._redis.evalsha(
                sha, 1, f"rl:{key}", self.capacity, self.refill, time.time(), tokens
            )
            return bool(result)
        except Exception as exc:  # noqa: BLE001
            # EVALSHA/SCRIPT unsupported (fakeredis) -> signal fallback; a real
            # connection error also lands here and is handled fail-open above.
            if _is_scripting_unsupported(exc):
                return None
            raise

    async def _consume_fallback(self, key: str, tokens: float) -> bool:
        """Non-atomic HMGET/HMSET token bucket for servers without Lua.

        Used only when scripting is unavailable (e.g. fakeredis in tests). Not
        safe across replicas, but correct single-process and good enough for the
        test/dev path; production Redis supports EVALSHA and uses the atomic path.
        """
        rk = f"rl:{key}"
        now = time.time()
        state = await self._redis.hmget(rk, "tokens", "last")
        cur = float(state[0]) if state and state[0] is not None else self.capacity
        last = float(state[1]) if state and state[1] is not None else now
        elapsed = max(0.0, now - last)
        cur = min(self.capacity, cur + elapsed * self.refill)
        allowed = cur >= tokens
        if allowed:
            cur -= tokens
        await self._redis.hmset(rk, {"tokens": cur, "last": now})
        await self._redis.expire(rk, 3600)
        return allowed

    async def check(self, key: str, tokens: float = 1.0) -> bool:
        """Return True if the request is allowed; False if rate-limited.

        Tries the atomic Lua path; falls back to a non-atomic path on servers
        without scripting; fails open on any genuine Redis error.
        """
        try:
            decision = await self._consume_lua(key, tokens)
            if decision is None:
                return await self._consume_fallback(key, tokens)
            return decision
        except Exception:
            return True

    async def remaining(self, key: str) -> int:
        """Approximate remaining tokens (best-effort, non-atomic)."""
        try:
            raw = await self._redis.hget(f"rl:{key}", "tokens")
            return int(float(raw)) if raw else int(self.capacity)
        except Exception:
            return int(self.capacity)

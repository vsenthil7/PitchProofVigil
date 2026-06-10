"""Health and readiness checks.

Liveness is trivial (the process is up). Readiness verifies dependencies —
here, that the database answers a trivial query. Each check returns a
structured result so the probe endpoint can report per-dependency status.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from sqlalchemy import text

from app.db.engine import Database


@dataclass
class CheckResult:
    name: str
    healthy: bool
    detail: str = ""
    latency_ms: float = 0.0


@dataclass
class ReadinessReport:
    ready: bool
    checks: list[CheckResult] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "ready": self.ready,
            "checks": [
                {
                    "name": c.name,
                    "healthy": c.healthy,
                    "detail": c.detail,
                    "latency_ms": round(c.latency_ms, 2),
                }
                for c in self.checks
            ],
        }


class HealthService:
    def __init__(self, database: Database, settings=None) -> None:
        self.database = database
        self.settings = settings

    async def check_database(self) -> CheckResult:
        start = time.perf_counter()
        try:
            async with self.database.session() as s:
                await s.execute(text("SELECT 1"))
            return CheckResult(
                "database",
                True,
                "ok",
                (time.perf_counter() - start) * 1000.0,
            )
        except Exception as exc:  # pragma: no cover - exercised via fake
            return CheckResult(
                "database",
                False,
                f"{type(exc).__name__}: {exc}",
                (time.perf_counter() - start) * 1000.0,
            )

    def check_encryption(self) -> CheckResult:
        """Encryption is configured. A derived dev key is healthy-but-degraded:
        it works, but production should set ENCRYPTION_KEYS, so we surface it as
        a non-fatal detail rather than failing readiness."""
        start = time.perf_counter()
        if self.settings is None:
            return CheckResult("encryption", True, "not evaluated", 0.0)
        from app.crypto import KeyProvider

        provider = KeyProvider(self.settings)
        detail = (
            f"ephemeral dev key (set ENCRYPTION_KEYS); ring={provider.key_count}"
            if provider.is_ephemeral
            else f"configured; ring={provider.key_count}"
        )
        return CheckResult(
            "encryption", True, detail, (time.perf_counter() - start) * 1000.0
        )

    async def check_migrations(self) -> CheckResult:
        """The DB schema is at the latest Alembic revision.

        Compares the version recorded in ``alembic_version`` against the head
        revision shipped in the image. A drift here means someone forgot to run
        migrations — a real readiness failure.
        """
        start = time.perf_counter()
        try:
            from app.db.migrations_info import head_revision

            expected = head_revision()
            async with self.database.session() as s:
                result = await s.execute(text("SELECT version_num FROM alembic_version"))
                current = result.scalar()
            healthy = current == expected
            detail = (
                "at head"
                if healthy
                else f"drift: db={current} head={expected}"
            )
            return CheckResult(
                "migrations", healthy, detail, (time.perf_counter() - start) * 1000.0
            )
        except Exception as exc:
            # No alembic_version table (e.g. schema created directly in tests):
            # treat as not-applicable rather than a hard failure.
            return CheckResult(
                "migrations",
                True,
                f"not tracked ({type(exc).__name__})",
                (time.perf_counter() - start) * 1000.0,
            )

    async def check_phoenix_mcp(self) -> CheckResult:
        """Phoenix MCP session is reachable (or degraded/mock).

        Degraded (session unavailable) is NOT a hard failure: Phoenix can come
        back, and the agent falls back to its local trace store meanwhile.
        """
        start = time.perf_counter()
        if self.settings is None or getattr(self.settings, "use_mocks", True):
            return CheckResult("phoenix_mcp", True, "mock mode", 0.0)
        try:
            from app.phoenix.mcp_client import PhoenixMCPClient

            client = PhoenixMCPClient(settings=self.settings)
            detail = (
                "connected"
                if client.connected
                else "degraded (session unavailable)"
            )
            return CheckResult(
                "phoenix_mcp",
                True,
                detail,
                (time.perf_counter() - start) * 1000.0,
            )
        except Exception as exc:  # pragma: no cover - defensive
            return CheckResult(
                "phoenix_mcp",
                True,
                f"check failed: {type(exc).__name__}",
                (time.perf_counter() - start) * 1000.0,
            )

    async def readiness(self) -> ReadinessReport:
        checks = [
            await self.check_database(),
            self.check_encryption(),
            await self.check_migrations(),
            await self.check_phoenix_mcp(),
        ]
        return ReadinessReport(ready=all(c.healthy for c in checks), checks=checks)

    @staticmethod
    def liveness() -> dict:
        return {"alive": True}

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
    def __init__(self, database: Database) -> None:
        self.database = database

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

    async def readiness(self) -> ReadinessReport:
        checks = [await self.check_database()]
        return ReadinessReport(ready=all(c.healthy for c in checks), checks=checks)

    @staticmethod
    def liveness() -> dict:
        return {"alive": True}

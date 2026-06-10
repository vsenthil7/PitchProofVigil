"""Analytics & trends service.

Computes time-bucketed views over persisted evaluations and traces: pass-rate
over time, per-category mean score trend, and per-evaluator failure trend. The
bucketing is done in Python over fetched rows so it works identically on
Postgres and SQLite (no dialect-specific date functions).
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import EvaluationRow, TraceRow


def _floor_to_bucket(ts: datetime, bucket_minutes: int) -> datetime:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    epoch_min = int(ts.timestamp() // 60)
    floored = epoch_min - (epoch_min % bucket_minutes)
    return datetime.fromtimestamp(floored * 60, tz=timezone.utc)


@dataclass
class TrendPoint:
    bucket: str  # ISO timestamp of bucket start
    value: float
    count: int


class AnalyticsService:
    """Tenant-scoped trend computations."""

    def __init__(self, session: AsyncSession, tenant_id: str) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def _evaluations_since(self, since: datetime) -> list[EvaluationRow]:
        stmt = select(EvaluationRow).where(
            EvaluationRow.tenant_id == self.tenant_id,
            EvaluationRow.created_at >= since,
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def _traces_since(self, since: datetime) -> list[TraceRow]:
        stmt = select(TraceRow).where(
            TraceRow.tenant_id == self.tenant_id,
            TraceRow.created_at >= since,
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def pass_rate_trend(
        self, window_hours: int = 24, bucket_minutes: int = 60
    ) -> list[TrendPoint]:
        """Fraction of evaluations with a passing verdict, per time bucket."""
        since = datetime.now(timezone.utc) - timedelta(hours=window_hours)
        rows = await self._evaluations_since(since)
        passed: dict[datetime, int] = defaultdict(int)
        total: dict[datetime, int] = defaultdict(int)
        for r in rows:
            b = _floor_to_bucket(r.created_at, bucket_minutes)
            total[b] += 1
            if r.verdict == "pass":
                passed[b] += 1
        return [
            TrendPoint(
                bucket=b.isoformat(),
                value=round(passed[b] / total[b], 4) if total[b] else 0.0,
                count=total[b],
            )
            for b in sorted(total)
        ]

    async def category_score_trend(
        self, category: str, window_hours: int = 24, bucket_minutes: int = 60
    ) -> list[TrendPoint]:
        """Mean score within a category, per time bucket."""
        since = datetime.now(timezone.utc) - timedelta(hours=window_hours)
        rows = [
            r for r in await self._evaluations_since(since) if r.category == category
        ]
        sums: dict[datetime, float] = defaultdict(float)
        counts: dict[datetime, int] = defaultdict(int)
        for r in rows:
            b = _floor_to_bucket(r.created_at, bucket_minutes)
            sums[b] += r.score
            counts[b] += 1
        return [
            TrendPoint(
                bucket=b.isoformat(),
                value=round(sums[b] / counts[b], 4) if counts[b] else 0.0,
                count=counts[b],
            )
            for b in sorted(counts)
        ]

    async def evaluator_failure_trend(
        self, evaluator: str, window_hours: int = 24, bucket_minutes: int = 60
    ) -> list[TrendPoint]:
        """Failure fraction for one evaluator, per time bucket."""
        since = datetime.now(timezone.utc) - timedelta(hours=window_hours)
        rows = [
            r for r in await self._evaluations_since(since) if r.evaluator == evaluator
        ]
        fails: dict[datetime, int] = defaultdict(int)
        total: dict[datetime, int] = defaultdict(int)
        for r in rows:
            b = _floor_to_bucket(r.created_at, bucket_minutes)
            total[b] += 1
            if r.verdict in ("fail", "error"):
                fails[b] += 1
        return [
            TrendPoint(
                bucket=b.isoformat(),
                value=round(fails[b] / total[b], 4) if total[b] else 0.0,
                count=total[b],
            )
            for b in sorted(total)
        ]

    async def latency_trend(
        self, window_hours: int = 24, bucket_minutes: int = 60
    ) -> list[TrendPoint]:
        """Mean agent latency (ms) per time bucket."""
        since = datetime.now(timezone.utc) - timedelta(hours=window_hours)
        rows = await self._traces_since(since)
        sums: dict[datetime, float] = defaultdict(float)
        counts: dict[datetime, int] = defaultdict(int)
        for r in rows:
            b = _floor_to_bucket(r.created_at, bucket_minutes)
            sums[b] += r.latency_ms
            counts[b] += 1
        return [
            TrendPoint(
                bucket=b.isoformat(),
                value=round(sums[b] / counts[b], 2) if counts[b] else 0.0,
                count=counts[b],
            )
            for b in sorted(counts)
        ]

    async def summary(self, window_hours: int = 24) -> dict:
        """Headline numbers for the window: total evals, overall pass rate."""
        since = datetime.now(timezone.utc) - timedelta(hours=window_hours)
        rows = await self._evaluations_since(since)
        total = len(rows)
        passed = sum(1 for r in rows if r.verdict == "pass")
        return {
            "window_hours": window_hours,
            "evaluations": total,
            "pass_rate": round(passed / total, 4) if total else 0.0,
        }

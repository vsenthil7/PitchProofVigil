"""Repository layer — async data access, tenant-scoped.

Repositories are the only place that touch the ORM. Every query is scoped by
tenant_id so cross-tenant reads are impossible by construction. Each repo takes
an AsyncSession; the unit-of-work is owned by the caller (the API dependency or
a service), keeping transactions explicit.
"""
from __future__ import annotations


from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import EvaluationRow, SpanRow, TraceRow


class TraceRepository:
    """Persists and queries traces and their spans, always tenant-scoped."""

    def __init__(self, session: AsyncSession, tenant_id: str) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def add(self, trace: TraceRow, spans: list[SpanRow]) -> TraceRow:
        trace.tenant_id = self.tenant_id
        self.session.add(trace)
        for span in spans:
            span.tenant_id = self.tenant_id
            span.trace_id = trace.id
            self.session.add(span)
        await self.session.flush()
        return trace

    async def get(self, trace_id: str) -> TraceRow | None:
        stmt = select(TraceRow).where(
            TraceRow.id == trace_id, TraceRow.tenant_id == self.tenant_id
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_spans(self, trace_id: str) -> list[SpanRow]:
        stmt = select(SpanRow).where(
            SpanRow.trace_id == trace_id, SpanRow.tenant_id == self.tenant_id
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def list(self, limit: int = 50, offset: int = 0) -> list[TraceRow]:
        stmt = (
            select(TraceRow)
            .where(TraceRow.tenant_id == self.tenant_id)
            .order_by(desc(TraceRow.created_at))
            .limit(limit)
            .offset(offset)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def count(self) -> int:
        stmt = select(func.count()).select_from(TraceRow).where(
            TraceRow.tenant_id == self.tenant_id
        )
        return int((await self.session.execute(stmt)).scalar_one())

    async def count_by_intent(self) -> dict[str, int]:
        stmt = (
            select(TraceRow.intent, func.count())
            .where(TraceRow.tenant_id == self.tenant_id)
            .group_by(TraceRow.intent)
        )
        rows = (await self.session.execute(stmt)).all()
        return {(intent or "unknown"): int(c) for intent, c in rows}


class EvaluationRepository:
    """Persists and aggregates evaluation outcomes."""

    def __init__(self, session: AsyncSession, tenant_id: str) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def add_many(self, rows: list[EvaluationRow]) -> None:
        for row in rows:
            row.tenant_id = self.tenant_id
            self.session.add(row)
        await self.session.flush()

    async def for_trace(self, trace_id: str) -> list[EvaluationRow]:
        stmt = select(EvaluationRow).where(
            EvaluationRow.trace_id == trace_id,
            EvaluationRow.tenant_id == self.tenant_id,
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def verdict_breakdown(self) -> dict[str, int]:
        stmt = (
            select(EvaluationRow.verdict, func.count())
            .where(EvaluationRow.tenant_id == self.tenant_id)
            .group_by(EvaluationRow.verdict)
        )
        rows = (await self.session.execute(stmt)).all()
        return {verdict: int(c) for verdict, c in rows}

    async def failure_rate_by_evaluator(self) -> dict[str, float]:
        """Fraction of FAIL/ERROR outcomes per evaluator."""
        stmt = select(
            EvaluationRow.evaluator,
            EvaluationRow.verdict,
            func.count(),
        ).where(EvaluationRow.tenant_id == self.tenant_id).group_by(
            EvaluationRow.evaluator, EvaluationRow.verdict
        )
        rows = (await self.session.execute(stmt)).all()
        totals: dict[str, int] = {}
        fails: dict[str, int] = {}
        for evaluator, verdict, count in rows:
            totals[evaluator] = totals.get(evaluator, 0) + int(count)
            if verdict in ("fail", "error"):
                fails[evaluator] = fails.get(evaluator, 0) + int(count)
        return {
            ev: round(fails.get(ev, 0) / total, 4)
            for ev, total in totals.items()
            if total
        }

    async def recent_mean_score(self, evaluator: str, limit: int = 100) -> float | None:
        stmt = (
            select(EvaluationRow.score)
            .where(
                EvaluationRow.tenant_id == self.tenant_id,
                EvaluationRow.evaluator == evaluator,
            )
            .order_by(desc(EvaluationRow.created_at))
            .limit(limit)
        )
        scores = list((await self.session.execute(stmt)).scalars().all())
        return sum(scores) / len(scores) if scores else None

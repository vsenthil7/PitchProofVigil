"""Analytics router: time-series trends over evaluations and traces."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics import AnalyticsService
from app.api.deps import db_session, require
from app.api.schemas.ops import AnalyticsSummaryOut, DriftPointOut, TrendPointOut
from app.auth.service import Permission, Principal

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _points(rows) -> list[TrendPointOut]:
    return [TrendPointOut(bucket=p.bucket, value=p.value, count=p.count) for p in rows]


@router.get("/summary", response_model=AnalyticsSummaryOut)
async def summary(
    window_hours: int = 24,
    principal: Principal = Depends(require(Permission.READ)),
    session: AsyncSession = Depends(db_session),
) -> AnalyticsSummaryOut:
    svc = AnalyticsService(session, principal.tenant_id)
    return AnalyticsSummaryOut(**await svc.summary(window_hours))


@router.get("/pass-rate", response_model=list[TrendPointOut])
async def pass_rate(
    window_hours: int = 24,
    bucket_minutes: int = 60,
    principal: Principal = Depends(require(Permission.READ)),
    session: AsyncSession = Depends(db_session),
) -> list[TrendPointOut]:
    svc = AnalyticsService(session, principal.tenant_id)
    return _points(await svc.pass_rate_trend(window_hours, bucket_minutes))


@router.get("/category/{category}", response_model=list[TrendPointOut])
async def category_trend(
    category: str,
    window_hours: int = 24,
    bucket_minutes: int = 60,
    principal: Principal = Depends(require(Permission.READ)),
    session: AsyncSession = Depends(db_session),
) -> list[TrendPointOut]:
    svc = AnalyticsService(session, principal.tenant_id)
    return _points(await svc.category_score_trend(category, window_hours, bucket_minutes))


@router.get("/evaluator/{evaluator}", response_model=list[TrendPointOut])
async def evaluator_trend(
    evaluator: str,
    window_hours: int = 24,
    bucket_minutes: int = 60,
    principal: Principal = Depends(require(Permission.READ)),
    session: AsyncSession = Depends(db_session),
) -> list[TrendPointOut]:
    svc = AnalyticsService(session, principal.tenant_id)
    return _points(await svc.evaluator_failure_trend(evaluator, window_hours, bucket_minutes))


@router.get("/latency", response_model=list[TrendPointOut])
async def latency_trend(
    window_hours: int = 24,
    bucket_minutes: int = 60,
    principal: Principal = Depends(require(Permission.READ)),
    session: AsyncSession = Depends(db_session),
) -> list[TrendPointOut]:
    svc = AnalyticsService(session, principal.tenant_id)
    return _points(await svc.latency_trend(window_hours, bucket_minutes))


@router.get("/drift/{evaluator}", response_model=list[DriftPointOut])
async def evaluator_drift(
    evaluator: str,
    window_hours: int = 168,
    bucket_minutes: int = 60,
    principal: Principal = Depends(require(Permission.READ)),
    session: AsyncSession = Depends(db_session),
) -> list[DriftPointOut]:
    """Time-bucketed drift for one evaluator: mean, p10, p90, pass_rate."""
    svc = AnalyticsService(session, principal.tenant_id)
    points = await svc.evaluator_drift(evaluator, window_hours, bucket_minutes)
    return [DriftPointOut(**p) for p in points]

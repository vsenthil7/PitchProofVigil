"""Tests for the analytics/trends service and router."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.analytics.trends import AnalyticsService, _floor_to_bucket
from app.db.models import EvaluationRow, TraceRow


def test_floor_to_bucket():
    ts = datetime(2026, 6, 1, 14, 37, 0, tzinfo=timezone.utc)
    floored = _floor_to_bucket(ts, 60)
    assert floored.minute == 0 and floored.hour == 14
    # naive datetime is treated as UTC
    naive = datetime(2026, 6, 1, 14, 37, 0)
    assert _floor_to_bucket(naive, 30).minute == 30


async def _seed(session, tenant_id):
    now = datetime.now(timezone.utc)
    # Two buckets an hour apart, mixed verdicts.
    rows = [
        EvaluationRow(tenant_id=tenant_id, trace_id="t1", evaluator="factual_accuracy",
                      version="1", category="correctness", verdict="pass", score=1.0,
                      confidence=1.0, summary="", created_at=now),
        EvaluationRow(tenant_id=tenant_id, trace_id="t1", evaluator="factual_accuracy",
                      version="1", category="correctness", verdict="fail", score=0.0,
                      confidence=1.0, summary="", created_at=now),
        EvaluationRow(tenant_id=tenant_id, trace_id="t2", evaluator="factual_accuracy",
                      version="1", category="correctness", verdict="pass", score=0.8,
                      confidence=1.0, summary="", created_at=now - timedelta(hours=1)),
    ]
    for r in rows:
        session.add(r)
    session.add(TraceRow(id="t1", tenant_id=tenant_id, request_text="q", language="en",
                         latency_ms=120.0, created_at=now))
    session.add(TraceRow(id="t2", tenant_id=tenant_id, request_text="q", language="en",
                         latency_ms=80.0, created_at=now - timedelta(hours=1)))
    await session.flush()


async def test_pass_rate_trend(db, tenant_id):
    async with db.session() as s:
        await _seed(s, tenant_id)
        svc = AnalyticsService(s, tenant_id)
        points = await svc.pass_rate_trend(window_hours=24, bucket_minutes=60)
        assert len(points) == 2
        # Most recent bucket: 1 pass / 2 total = 0.5
        assert points[-1].value == 0.5
        assert points[-1].count == 2


async def test_category_score_trend(db, tenant_id):
    async with db.session() as s:
        await _seed(s, tenant_id)
        svc = AnalyticsService(s, tenant_id)
        points = await svc.category_score_trend("correctness", 24, 60)
        assert len(points) == 2
        assert points[-1].value == 0.5  # mean of 1.0 and 0.0


async def test_category_trend_empty_for_unknown(db, tenant_id):
    async with db.session() as s:
        await _seed(s, tenant_id)
        svc = AnalyticsService(s, tenant_id)
        assert await svc.category_score_trend("nonexistent", 24, 60) == []


async def test_evaluator_failure_trend(db, tenant_id):
    async with db.session() as s:
        await _seed(s, tenant_id)
        svc = AnalyticsService(s, tenant_id)
        points = await svc.evaluator_failure_trend("factual_accuracy", 24, 60)
        assert points[-1].value == 0.5  # 1 fail / 2


async def test_latency_trend(db, tenant_id):
    async with db.session() as s:
        await _seed(s, tenant_id)
        svc = AnalyticsService(s, tenant_id)
        points = await svc.latency_trend(24, 60)
        assert points[-1].value == 120.0
        assert points[0].value == 80.0


async def test_summary(db, tenant_id):
    async with db.session() as s:
        await _seed(s, tenant_id)
        svc = AnalyticsService(s, tenant_id)
        summary = await svc.summary(24)
        assert summary["evaluations"] == 3
        assert summary["pass_rate"] == round(2 / 3, 4)


async def test_summary_empty(db, tenant_id):
    async with db.session() as s:
        svc = AnalyticsService(s, tenant_id)
        summary = await svc.summary(24)
        assert summary["evaluations"] == 0
        assert summary["pass_rate"] == 0.0


# ---- Router ----

def test_analytics_endpoints(owner_auth):
    client, headers, _ = owner_auth
    # Generate some data through the live flow.
    client.post("/api/ask", headers=headers, json={"text": "I want to buy a ticket"})
    client.post("/api/ask", headers=headers, json={"text": "which gate do I use"})

    summary = client.get("/api/analytics/summary", headers=headers).json()
    assert summary["evaluations"] > 0

    pr = client.get("/api/analytics/pass-rate", headers=headers).json()
    assert isinstance(pr, list) and len(pr) >= 1

    cat = client.get("/api/analytics/category/correctness", headers=headers).json()
    assert isinstance(cat, list)

    ev = client.get("/api/analytics/evaluator/factual_accuracy", headers=headers).json()
    assert isinstance(ev, list)

    lat = client.get("/api/analytics/latency", headers=headers).json()
    assert isinstance(lat, list) and len(lat) >= 1


async def test_evaluator_drift_percentile_branch(db, tenant_id):
    """>=10 scores in a bucket exercises the p10/p90 percentile path."""
    now = datetime.now(timezone.utc)
    async with db.session() as s:
        for i in range(20):
            s.add(
                EvaluationRow(
                    tenant_id=tenant_id, trace_id="td", evaluator="llm_judge",
                    version="2", category="quality", verdict="pass",
                    score=round(0.5 + i * 0.02, 4), confidence=0.9, summary="",
                    created_at=now,
                )
            )
        await s.flush()
        svc = AnalyticsService(s, tenant_id)
        result = await svc.evaluator_drift("llm_judge", window_hours=24, bucket_minutes=60)
    assert len(result) >= 1
    pt = result[-1]
    assert pt["count"] == 20
    assert 0.0 <= pt["p10"] <= pt["mean_score"] <= pt["p90"] <= 1.0
    assert "pass_rate" in pt


async def test_evaluator_drift_small_bucket_branch(db, tenant_id):
    """<10 scores uses the min/max fallback for p10/p90."""
    now = datetime.now(timezone.utc)
    async with db.session() as s:
        for sc in (0.3, 0.9, 0.6):
            s.add(
                EvaluationRow(
                    tenant_id=tenant_id, trace_id="ts", evaluator="latency_slo",
                    version="2", category="performance", verdict="pass",
                    score=sc, confidence=0.9, summary="", created_at=now,
                )
            )
        await s.flush()
        svc = AnalyticsService(s, tenant_id)
        result = await svc.evaluator_drift("latency_slo", window_hours=24)
    pt = result[-1]
    assert pt["count"] == 3
    assert pt["p10"] == 0.3  # min
    assert pt["p90"] == 0.9  # max


def test_drift_endpoint(owner_auth):
    client, headers, _ = owner_auth
    client.post("/api/ask", headers=headers, json={"text": "I want to buy a ticket"})
    # llm_judge runs on every ask; drift endpoint should return JSON list.
    r = client.get("/api/analytics/drift/llm_judge", headers=headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)

"""Tests for CostBudgetEnforcer (P6.M4) and the admin cost-budget endpoints."""
from __future__ import annotations

from datetime import datetime, timezone

from app.db.models.governance import CostBudgetRow, CostEventRow
from app.orchestration.cost import CostBudgetEnforcer

_MONTH = datetime.now(timezone.utc).strftime("%Y-%m")


async def test_enforcer_allows_when_no_budget(db, tenant_id):
    async with db.session() as s:
        allowed, reason = await CostBudgetEnforcer(s, tenant_id).check_budget()
    assert allowed is True
    assert reason == "no_budget_configured"


async def test_enforcer_blocks_when_over_cap(db, tenant_id):
    async with db.session() as s:
        s.add(CostBudgetRow(tenant_id=tenant_id, monthly_usd_cap=0.0,
                            alert_threshold_pct=0.8, month=_MONTH))
        await s.flush()
        allowed, reason = await CostBudgetEnforcer(s, tenant_id).check_budget(
            estimated_cost_usd=0.001
        )
    assert allowed is False
    assert "BUDGET_EXCEEDED" in reason


async def test_enforcer_threshold_alert(db, tenant_id):
    """At/above the alert threshold but under cap -> allowed with alert reason."""
    async with db.session() as s:
        s.add(CostBudgetRow(tenant_id=tenant_id, monthly_usd_cap=1.0,
                            alert_threshold_pct=0.8, month=_MONTH))
        # Already spent 0.85 (>= 0.8 threshold, < 1.0 cap).
        s.add(CostEventRow(tenant_id=tenant_id, month=_MONTH, model="gemini",
                           input_tokens=10, output_tokens=10, cost_usd=0.85))
        await s.flush()
        allowed, reason = await CostBudgetEnforcer(s, tenant_id).check_budget(
            estimated_cost_usd=0.001
        )
    assert allowed is True
    assert "BUDGET_THRESHOLD_ALERT" in reason


async def test_enforcer_ok_under_threshold(db, tenant_id):
    async with db.session() as s:
        s.add(CostBudgetRow(tenant_id=tenant_id, monthly_usd_cap=10.0,
                            alert_threshold_pct=0.8, month=_MONTH))
        s.add(CostEventRow(tenant_id=tenant_id, month=_MONTH, model="gemini",
                           input_tokens=5, output_tokens=5, cost_usd=0.10))
        await s.flush()
        allowed, reason = await CostBudgetEnforcer(s, tenant_id).check_budget(
            estimated_cost_usd=0.001
        )
    assert allowed is True
    assert reason == "ok"


async def test_enforcer_record_event_persists(db, tenant_id):
    async with db.session() as s:
        await CostBudgetEnforcer(s, tenant_id).record_event(
            model="gemini-2.5", input_tokens=100, output_tokens=50, cost_usd=0.02
        )
        from sqlalchemy import func, select
        total = (await s.execute(
            select(func.sum(CostEventRow.cost_usd)).where(
                CostEventRow.tenant_id == tenant_id
            )
        )).scalar()
    assert total == 0.02


# ---- API-level (owner_auth has ADMIN via OWNER role) ----

def test_create_and_read_cost_budget_endpoint(owner_auth):
    client, headers, _ = owner_auth
    r = client.post(
        "/api/admin/cost-budgets",
        headers=headers,
        json={"monthly_usd_cap": 25.0, "alert_threshold_pct": 0.75, "month": _MONTH},
    )
    assert r.status_code == 201, r.text
    assert r.json()["monthly_usd_cap"] == 25.0

    cur = client.get("/api/admin/cost-budgets/current", headers=headers)
    assert cur.status_code == 200
    data = cur.json()
    assert data["configured"] is True
    assert data["monthly_usd_cap"] == 25.0
    assert data["current_spend_usd"] == 0.0


def test_current_spend_unconfigured(owner_auth):
    client, headers, _ = owner_auth
    cur = client.get("/api/admin/cost-budgets/current", headers=headers).json()
    assert cur["configured"] is False
    assert cur["monthly_usd_cap"] is None

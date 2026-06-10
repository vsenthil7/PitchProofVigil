"""Admin router: health, readiness, and Prometheus metrics."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session, get_db, get_metrics_dep, require
from app.auth.service import Permission, Principal
from app.observability.health import HealthService

router = APIRouter(tags=["admin"])


class CostBudgetRequest(BaseModel):
    monthly_usd_cap: float = Field(..., ge=0.0)
    alert_threshold_pct: float = Field(default=0.8, ge=0.0, le=1.0)
    month: str  # "YYYY-MM"


@router.get("/health")
async def health() -> dict:
    return HealthService.liveness()


@router.get("/ready")
async def ready(request: Request) -> dict:
    hs = HealthService(get_db(request), settings=request.app.state.settings)
    report = await hs.readiness()
    return report.as_dict()


@router.get("/metrics")
async def metrics(request: Request) -> Response:
    data, content_type = get_metrics_dep(request).render()
    return Response(content=data, media_type=content_type)


@router.get("/api/security/status")
async def security_status(request: Request) -> dict:
    """Report encryption posture (no secrets, just config health)."""
    from app.crypto import KeyProvider

    provider = KeyProvider(request.app.state.settings)
    return {
        "encryption_at_rest": True,
        "key_ring_size": provider.key_count,
        "using_ephemeral_dev_key": provider.is_ephemeral,
        "rotation_supported": True,
    }


@router.post("/api/admin/cost-budgets", status_code=201)
async def create_cost_budget(
    body: CostBudgetRequest,
    principal: Principal = Depends(require(Permission.ADMIN)),
    session: AsyncSession = Depends(db_session),
) -> dict:
    """Set a monthly LLM-cost cap for the caller's tenant (ADMIN only)."""
    from app.db.models.governance import CostBudgetRow

    row = CostBudgetRow(
        tenant_id=principal.tenant_id,
        monthly_usd_cap=body.monthly_usd_cap,
        alert_threshold_pct=body.alert_threshold_pct,
        month=body.month,
    )
    session.add(row)
    await session.flush()
    return {
        "id": row.id,
        "tenant_id": row.tenant_id,
        "monthly_usd_cap": row.monthly_usd_cap,
        "alert_threshold_pct": row.alert_threshold_pct,
        "month": row.month,
    }


@router.get("/api/admin/cost-budgets/current")
async def get_current_spend(
    principal: Principal = Depends(require(Permission.READ)),
    session: AsyncSession = Depends(db_session),
) -> dict:
    """Report the caller tenant's current-month spend vs cap."""
    from datetime import datetime, timezone

    from sqlalchemy import func, select

    from app.db.models.governance import CostBudgetRow, CostEventRow

    month = datetime.now(timezone.utc).strftime("%Y-%m")
    budget = (
        await session.execute(
            select(CostBudgetRow).where(
                CostBudgetRow.tenant_id == principal.tenant_id,
                CostBudgetRow.month == month,
            )
        )
    ).scalars().first()
    spend = (
        await session.execute(
            select(func.sum(CostEventRow.cost_usd)).where(
                CostEventRow.tenant_id == principal.tenant_id,
                CostEventRow.month == month,
            )
        )
    ).scalar() or 0.0
    return {
        "month": month,
        "current_spend_usd": round(float(spend), 6),
        "monthly_usd_cap": budget.monthly_usd_cap if budget else None,
        "configured": budget is not None,
    }


@router.delete("/api/admin/tenants/{tenant_id}/data")
async def erase_tenant_data(
    tenant_id: str,
    principal: Principal = Depends(require(Permission.ADMIN)),
    session: AsyncSession = Depends(db_session),
) -> Response:
    """GDPR right-to-erasure: hard-delete all tenant data in one transaction.

    Only the OWNER may erase, and only their own tenant. Deletes every
    tenant-scoped table (those carrying a tenant_id column) plus child rows
    (spans via their trace ids), then the tenant row itself.
    """
    from sqlalchemy import delete, select

    from app.db.models import (
        AlertRow,
        APIKey,
        AuditLogRow,
        ComplianceExportJobRow,
        CostBudgetRow,
        CostEventRow,
        EvaluationRow,
        ExperimentItemResultRow,
        ExperimentRow,
        ExperimentRunRow,
        GateDecisionRow,
        GatePolicyRow,
        GoldenDatasetRow,
        SpanRow,
        SSOConfigRow,
        Tenant,
        TenantMembership,
        TraceRow,
        User,
    )

    if principal.role.value != "owner":  # pragma: no cover - role guard; needs a non-owner member token over a shared DB connection
        raise HTTPException(status_code=403, detail="Only OWNER can erase tenant data.")
    if principal.tenant_id != tenant_id:
        raise HTTPException(
            status_code=403, detail="OWNER may only erase their own tenant."
        )

    # Spans are keyed by trace_id, not tenant_id: delete them via this tenant's traces.
    trace_ids = list(
        (
            await session.execute(
                select(TraceRow.id).where(TraceRow.tenant_id == tenant_id)
            )
        )
        .scalars()
        .all()
    )
    if trace_ids:
        await session.execute(delete(SpanRow).where(SpanRow.trace_id.in_(trace_ids)))

    # All tenant-scoped tables, child-first to respect FKs.
    tenant_scoped = [
        ExperimentItemResultRow,
        ExperimentRunRow,
        ExperimentRow,
        CostEventRow,
        CostBudgetRow,
        ComplianceExportJobRow,
        EvaluationRow,
        AuditLogRow,
        AlertRow,
        GateDecisionRow,
        GoldenDatasetRow,
        GatePolicyRow,
        SSOConfigRow,
        TraceRow,
        APIKey,
        TenantMembership,
        User,
    ]
    for model in tenant_scoped:
        await session.execute(delete(model).where(model.tenant_id == tenant_id))

    await session.execute(delete(Tenant).where(Tenant.id == tenant_id))
    await session.flush()
    return Response(status_code=204)

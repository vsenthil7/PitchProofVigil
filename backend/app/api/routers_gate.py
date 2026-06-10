"""Gate, policy, dataset, and admin/observability routers."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    active_policy,
    db_session,
    get_db,
    get_metrics_dep,
    get_orchestrator,
    get_scoring_engine,
    require,
)
from app.api.schemas_v2 import (
    CreateDatasetRequest,
    DatasetResponse,
    EvaluatorSpecOut,
    GateDatasetRequest,
    GateRequest,
    GateResponse,
    PolicyResponse,
    PolicyUpsertRequest,
)
from app.auth.service import Permission, Principal
from app.datasets.gate_service import GateService
from app.db.models import GatePolicyRow, GoldenDatasetRow
from app.evaluators.scoring import GatePolicy, ScoringEngine
from app.observability.health import HealthService
from app.repositories.registry import (
    GateDecisionRepository,
    GatePolicyRepository,
    GoldenDatasetRepository,
)

gate_router = APIRouter(prefix="/api/gate", tags=["gate"])
policy_router = APIRouter(prefix="/api/policies", tags=["policies"])
dataset_router = APIRouter(prefix="/api/datasets", tags=["datasets"])
admin_router = APIRouter(tags=["admin"])


def _gate_response(d) -> GateResponse:
    return GateResponse(
        decision_id=d.decision_id,
        candidate=d.candidate,
        passed=d.passed,
        aggregate_score=d.aggregate_score,
        threshold=d.threshold,
        category_scores=d.category_scores,
        baseline_deltas=d.baseline_deltas,
        regressions=d.regressions,
        reason=d.reason,
        trace_count=d.total_traces(),
    )


def _gate_service(request, session, engine, principal) -> GateService:
    return GateService(
        tenant_id=principal.tenant_id,
        orchestrator=get_orchestrator(request),
        engine=engine,
        golden_repo=GoldenDatasetRepository(session, principal.tenant_id),
        decision_repo=GateDecisionRepository(session, principal.tenant_id),
        metrics=get_metrics_dep(request),
    )


@gate_router.post("", response_model=GateResponse)
async def run_gate(
    body: GateRequest,
    request: Request,
    principal: Principal = Depends(require(Permission.EVALUATE)),
    session: AsyncSession = Depends(db_session),
    engine: ScoringEngine = Depends(get_scoring_engine),
    policy: GatePolicy = Depends(active_policy),
) -> GateResponse:
    service = _gate_service(request, session, engine, principal)
    decision = await service.run_inline(
        body.candidate, body.queries, policy, body.language
    )
    return _gate_response(decision)


@gate_router.post("/dataset", response_model=GateResponse)
async def run_gate_dataset(
    body: GateDatasetRequest,
    request: Request,
    principal: Principal = Depends(require(Permission.EVALUATE)),
    session: AsyncSession = Depends(db_session),
    engine: ScoringEngine = Depends(get_scoring_engine),
    policy: GatePolicy = Depends(active_policy),
) -> GateResponse:
    service = _gate_service(request, session, engine, principal)
    decision = await service.run_candidate(body.candidate, body.dataset, policy)
    return _gate_response(decision)


@gate_router.get("/decisions")
async def list_decisions(
    limit: int = 50,
    principal: Principal = Depends(require(Permission.READ)),
    session: AsyncSession = Depends(db_session),
) -> list[dict]:
    repo = GateDecisionRepository(session, principal.tenant_id)
    rows = await repo.list(limit=limit)
    return [
        {
            "decision_id": r.id,
            "candidate": r.candidate,
            "passed": r.passed,
            "aggregate_score": r.aggregate_score,
            "category_scores": r.category_scores,
            "regressions": r.regressions,
            "reason": r.reason,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


# ---- Policies ----


@policy_router.get("/evaluators", response_model=list[EvaluatorSpecOut])
async def list_evaluators(
    principal: Principal = Depends(require(Permission.READ)),
    engine: ScoringEngine = Depends(get_scoring_engine),
) -> list[EvaluatorSpecOut]:
    return [
        EvaluatorSpecOut(
            name=s.name,
            version=s.version,
            category=s.category.value,
            title=s.title,
            description=s.description,
            default_weight=s.default_weight,
            blocking_by_default=s.blocking_by_default,
        )
        for s in engine.registry.specs()
    ]


@policy_router.post("", response_model=PolicyResponse, status_code=201)
async def upsert_policy(
    body: PolicyUpsertRequest,
    principal: Principal = Depends(require(Permission.MANAGE_POLICIES)),
    session: AsyncSession = Depends(db_session),
) -> PolicyResponse:
    repo = GatePolicyRepository(session, principal.tenant_id)
    row = await repo.upsert(
        GatePolicyRow(
            tenant_id=principal.tenant_id,
            name=body.name,
            threshold=body.threshold,
            fail_on_any_blocking=body.fail_on_any_blocking,
            evaluator_policies={
                k: v.model_dump() for k, v in body.evaluator_policies.items()
            },
        )
    )
    return PolicyResponse(
        id=row.id,
        name=row.name,
        version=row.version,
        threshold=row.threshold,
        fail_on_any_blocking=row.fail_on_any_blocking,
        evaluator_policies=row.evaluator_policies,
        is_active=row.is_active,
    )


@policy_router.get("", response_model=list[PolicyResponse])
async def list_policies(
    principal: Principal = Depends(require(Permission.READ)),
    session: AsyncSession = Depends(db_session),
) -> list[PolicyResponse]:
    repo = GatePolicyRepository(session, principal.tenant_id)
    rows = await repo.list()
    return [
        PolicyResponse(
            id=r.id,
            name=r.name,
            version=r.version,
            threshold=r.threshold,
            fail_on_any_blocking=r.fail_on_any_blocking,
            evaluator_policies=r.evaluator_policies,
            is_active=r.is_active,
        )
        for r in rows
    ]


# ---- Datasets ----


@dataset_router.post("", response_model=DatasetResponse, status_code=201)
async def create_dataset(
    body: CreateDatasetRequest,
    principal: Principal = Depends(require(Permission.WRITE)),
    session: AsyncSession = Depends(db_session),
) -> DatasetResponse:
    repo = GoldenDatasetRepository(session, principal.tenant_id)
    if await repo.get(body.name) is not None:
        raise HTTPException(status_code=409, detail="dataset exists")
    row = await repo.create(
        GoldenDatasetRow(
            tenant_id=principal.tenant_id,
            name=body.name,
            description=body.description,
            examples=body.examples,
        )
    )
    return DatasetResponse(
        id=row.id, name=row.name, description=row.description, example_count=len(row.examples)
    )


@dataset_router.get("", response_model=list[DatasetResponse])
async def list_datasets(
    principal: Principal = Depends(require(Permission.READ)),
    session: AsyncSession = Depends(db_session),
) -> list[DatasetResponse]:
    repo = GoldenDatasetRepository(session, principal.tenant_id)
    rows = await repo.list()
    return [
        DatasetResponse(
            id=r.id, name=r.name, description=r.description, example_count=len(r.examples)
        )
        for r in rows
    ]


# ---- Admin / observability ----


@admin_router.get("/health")
async def health() -> dict:
    return HealthService.liveness()


@admin_router.get("/ready")
async def ready(request: Request) -> dict:
    hs = HealthService(get_db(request))
    report = await hs.readiness()
    return report.as_dict()


@admin_router.get("/metrics")
async def metrics(request: Request) -> Response:
    data, content_type = get_metrics_dep(request).render()
    return Response(content=data, media_type=content_type)

"""Gate router: run a candidate over inline queries or a stored dataset."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import active_policy, db_session, get_scoring_engine, require
from app.api.routers._helpers import build_gate_service, gate_response
from app.api.schemas import GateDatasetRequest, GateRequest, GateResponse
from app.auth.service import Permission, Principal
from app.evaluators.scoring import GatePolicy, ScoringEngine
from app.repositories.registry import GateDecisionRepository

router = APIRouter(prefix="/api/gate", tags=["gate"])


@router.post("", response_model=GateResponse)
async def run_gate(
    body: GateRequest,
    request: Request,
    principal: Principal = Depends(require(Permission.EVALUATE)),
    session: AsyncSession = Depends(db_session),
    engine: ScoringEngine = Depends(get_scoring_engine),
    policy: GatePolicy = Depends(active_policy),
) -> GateResponse:
    service = build_gate_service(request, session, engine, principal)
    decision = await service.run_inline(
        body.candidate, body.queries, policy, body.language
    )
    return gate_response(decision)


@router.post("/dataset", response_model=GateResponse)
async def run_gate_dataset(
    body: GateDatasetRequest,
    request: Request,
    principal: Principal = Depends(require(Permission.EVALUATE)),
    session: AsyncSession = Depends(db_session),
    engine: ScoringEngine = Depends(get_scoring_engine),
    policy: GatePolicy = Depends(active_policy),
) -> GateResponse:
    service = build_gate_service(request, session, engine, principal)
    decision = await service.run_candidate(body.candidate, body.dataset, policy)
    return gate_response(decision)


@router.get("/decisions")
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

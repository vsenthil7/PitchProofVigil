"""Policy router: evaluator catalog + versioned gate policies."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session, get_scoring_engine, require
from app.api.schemas import (
    EvaluatorSpecOut,
    PolicyResponse,
    PolicyUpsertRequest,
)
from app.auth.service import Permission, Principal
from app.db.models import GatePolicyRow
from app.evaluators.scoring import ScoringEngine
from app.repositories.registry import GatePolicyRepository

router = APIRouter(prefix="/api/policies", tags=["policies"])


def _to_response(row: GatePolicyRow) -> PolicyResponse:
    return PolicyResponse(
        id=row.id,
        name=row.name,
        version=row.version,
        threshold=row.threshold,
        fail_on_any_blocking=row.fail_on_any_blocking,
        evaluator_policies=row.evaluator_policies,
        is_active=row.is_active,
    )


@router.get("/evaluators", response_model=list[EvaluatorSpecOut])
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


@router.post("", response_model=PolicyResponse, status_code=201)
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
    return _to_response(row)


@router.get("", response_model=list[PolicyResponse])
async def list_policies(
    principal: Principal = Depends(require(Permission.READ)),
    session: AsyncSession = Depends(db_session),
) -> list[PolicyResponse]:
    repo = GatePolicyRepository(session, principal.tenant_id)
    return [_to_response(r) for r in await repo.list()]

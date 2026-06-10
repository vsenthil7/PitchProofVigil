"""Shared helpers for the gate-family routers."""
from __future__ import annotations

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_metrics_dep, get_orchestrator
from app.api.schemas import GateResponse
from app.auth.service import Principal
from app.datasets.gate_service import GateService
from app.evaluators.candidate_gate import CandidateGateResult
from app.evaluators.scoring import ScoringEngine
from app.repositories.registry import (
    GateDecisionRepository,
    GoldenDatasetRepository,
)


def gate_response(d: CandidateGateResult) -> GateResponse:
    """Map a CandidateGateResult to its API representation."""
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


def build_gate_service(
    request: Request,
    session: AsyncSession,
    engine: ScoringEngine,
    principal: Principal,
) -> GateService:
    """Assemble a tenant-scoped GateService from request singletons."""
    return GateService(
        tenant_id=principal.tenant_id,
        orchestrator=get_orchestrator(request),
        engine=engine,
        golden_repo=GoldenDatasetRepository(session, principal.tenant_id),
        decision_repo=GateDecisionRepository(session, principal.tenant_id),
        metrics=get_metrics_dep(request),
    )

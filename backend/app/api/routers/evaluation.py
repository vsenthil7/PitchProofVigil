"""Evaluation router: ask the agent (with live scoring) and read traces."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    active_policy,
    db_session,
    get_metrics_dep,
    get_orchestrator,
    get_scoring_engine,
    require,
)
from app.api.schemas import AskRequest, AskResponse, EvalOut, FindingOut
from app.alerting.service import AlertingService
from app.auth.service import Permission, Principal
from app.core.models import ConciergeRequest
from app.datasets.eval_service import EvaluationService
from app.evaluators.scoring import GatePolicy, ScoringEngine
from app.repositories.registry import AlertRepository
from app.repositories.traces import EvaluationRepository, TraceRepository

router = APIRouter(prefix="/api", tags=["evaluation"])


@router.post("/ask", response_model=AskResponse)
async def ask(
    body: AskRequest,
    request: Request,
    principal: Principal = Depends(require(Permission.EVALUATE)),
    session: AsyncSession = Depends(db_session),
    engine: ScoringEngine = Depends(get_scoring_engine),
    policy: GatePolicy = Depends(active_policy),
) -> AskResponse:
    orchestrator = get_orchestrator(request)
    metrics = get_metrics_dep(request)
    # Wire a per-request event bus: audit handler persists, metrics handler
    # records gate movements. Decouples side-effects from the core workflow.
    from app.events.bus import EventBus
    from app.events.handlers import AuditHandler
    from app.repositories.audit import AuditRepository

    bus = EventBus()
    bus.subscribe_all(AuditHandler(AuditRepository(session, principal.tenant_id)))
    service = EvaluationService(
        tenant_id=principal.tenant_id,
        orchestrator=orchestrator,
        engine=engine,
        trace_repo=TraceRepository(session, principal.tenant_id),
        eval_repo=EvaluationRepository(session, principal.tenant_id),
        alerting=AlertingService(AlertRepository(session, principal.tenant_id)),
        metrics=metrics,
        bus=bus,
    )
    outcome = await service.ask(
        ConciergeRequest(text=body.text, language=body.language), policy
    )
    resp = outcome.trace.response
    return AskResponse(
        trace_id=outcome.trace.trace_id,
        answer=resp.text,
        intent=resp.detected_intent.value,
        model=resp.model,
        latency_ms=resp.latency_ms,
        aggregate_score=outcome.report.aggregate_score,
        passed=outcome.report.passed,
        reason=outcome.report.reason,
        category_scores=outcome.report.by_category(),
        evaluations=[
            EvalOut(
                evaluator=s.outcome.evaluator,
                category=s.outcome.category.value,
                verdict=s.outcome.verdict.value,
                score=s.outcome.score,
                confidence=s.outcome.confidence,
                summary=s.outcome.summary,
                findings=[
                    FindingOut(
                        code=f.code,
                        message=f.message,
                        severity=f.severity.value,
                        evidence=f.evidence,
                    )
                    for f in s.outcome.findings
                ],
                duration_ms=s.outcome.duration_ms,
            )
            for s in outcome.report.scored
        ],
        cost=outcome.cost,
        tool_calls=outcome.tool_calls,
    )


@router.get("/traces")
async def list_traces(
    limit: int = 50,
    principal: Principal = Depends(require(Permission.READ)),
    session: AsyncSession = Depends(db_session),
) -> list[dict]:
    repo = TraceRepository(session, principal.tenant_id)
    rows = await repo.list(limit=limit)
    return [
        {
            "trace_id": r.id,
            "request_text": r.request_text,
            "intent": r.intent,
            "response_text": r.response_text,
            "latency_ms": r.latency_ms,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


@router.get("/traces/{trace_id}")
async def get_trace(
    trace_id: str,
    principal: Principal = Depends(require(Permission.READ)),
    session: AsyncSession = Depends(db_session),
) -> dict:
    repo = TraceRepository(session, principal.tenant_id)
    row = await repo.get(trace_id)
    if row is None:
        raise HTTPException(status_code=404, detail="trace not found")
    spans = await repo.get_spans(trace_id)
    evals = await EvaluationRepository(session, principal.tenant_id).for_trace(trace_id)
    return {
        "trace_id": row.id,
        "request_text": row.request_text,
        "intent": row.intent,
        "response_text": row.response_text,
        "grounded_facts": row.grounded_facts,
        "spans": [
            {"name": s.name, "kind": s.kind, "status": s.status, "duration_ms": s.duration_ms}
            for s in spans
        ],
        "evaluations": [
            {
                "evaluator": e.evaluator,
                "verdict": e.verdict,
                "score": e.score,
                "summary": e.summary,
            }
            for e in evals
        ],
    }


@router.get("/stats")
async def stats(
    principal: Principal = Depends(require(Permission.READ)),
    session: AsyncSession = Depends(db_session),
) -> dict:
    traces = TraceRepository(session, principal.tenant_id)
    evals = EvaluationRepository(session, principal.tenant_id)
    return {
        "trace_count": await traces.count(),
        "by_intent": await traces.count_by_intent(),
        "verdict_breakdown": await evals.verdict_breakdown(),
        "failure_rate_by_evaluator": await evals.failure_rate_by_evaluator(),
    }

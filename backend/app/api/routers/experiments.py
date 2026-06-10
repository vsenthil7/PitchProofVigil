"""Experiment management router: CRUD, run, run-detail, compare."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session, get_scoring_engine, require
from app.auth.service import Permission, Principal
from app.evaluators.scoring import ScoringEngine
from app.experiments.service import ExperimentService

router = APIRouter(prefix="/api/experiments", tags=["experiments"])


class CreateExperimentRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    dataset_id: str
    evaluator_ids: list[str] = Field(default_factory=list)
    description: str = ""


class ExperimentOut(BaseModel):
    id: str
    name: str
    description: str
    dataset_id: str
    evaluator_ids: list[str]
    last_run_at: str | None


class RunOut(BaseModel):
    run_id: str
    status: str
    aggregate_score: float | None
    verdict_summary: dict
    completed_at: str | None


class ABCompareRequest(BaseModel):
    baseline_agent_version: str
    candidate_agent_version: str
    dataset_id: str
    evaluator_ids: list[str] = Field(default_factory=lambda: ["llm_judge"])


def _to_out(row) -> ExperimentOut:
    return ExperimentOut(
        id=row.id,
        name=row.name,
        description=row.description,
        dataset_id=row.dataset_id,
        evaluator_ids=row.evaluator_ids,
        last_run_at=row.last_run_at.isoformat() if row.last_run_at else None,
    )


@router.post("", response_model=ExperimentOut, status_code=201)
async def create_experiment(
    body: CreateExperimentRequest,
    principal: Principal = Depends(require(Permission.WRITE)),
    session: AsyncSession = Depends(db_session),
) -> ExperimentOut:
    svc = ExperimentService(session, principal.tenant_id)
    row = await svc.create(
        name=body.name,
        dataset_id=body.dataset_id,
        evaluator_ids=body.evaluator_ids,
        description=body.description,
    )
    return _to_out(row)


@router.get("", response_model=list[ExperimentOut])
async def list_experiments(
    principal: Principal = Depends(require(Permission.READ)),
    session: AsyncSession = Depends(db_session),
) -> list[ExperimentOut]:
    svc = ExperimentService(session, principal.tenant_id)
    return [_to_out(r) for r in await svc.list()]


@router.post("/{experiment_id}/run", response_model=RunOut)
async def trigger_run(
    experiment_id: str,
    principal: Principal = Depends(require(Permission.EVALUATE)),
    session: AsyncSession = Depends(db_session),
    engine: ScoringEngine = Depends(get_scoring_engine),
) -> RunOut:
    svc = ExperimentService(session, principal.tenant_id)
    try:
        run = await svc.trigger_run(experiment_id, engine.registry)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return RunOut(
        run_id=run.id,
        status=run.status,
        aggregate_score=run.aggregate_score,
        verdict_summary=run.verdict_summary,
        completed_at=run.completed_at.isoformat() if run.completed_at else None,
    )


@router.get("/{experiment_id}/runs/{run_id}")
async def get_run(
    experiment_id: str,
    run_id: str,
    principal: Principal = Depends(require(Permission.READ)),
    session: AsyncSession = Depends(db_session),
) -> dict:
    svc = ExperimentService(session, principal.tenant_id)
    run = await svc.get_run(run_id)
    if run is None or run.experiment_id != experiment_id:
        raise HTTPException(status_code=404, detail="run not found")
    items = await svc.get_run_items(run_id)
    return {
        "run_id": run.id,
        "status": run.status,
        "aggregate_score": run.aggregate_score,
        "verdict_summary": run.verdict_summary,
        "items": [
            {
                "index": r.example_index,
                "request_text": r.request_text,
                "verdicts": r.verdicts,
                "aggregate_score": r.aggregate_score,
                "passed": r.passed,
            }
            for r in items
        ],
    }


@router.get("/{experiment_id}/compare")
async def compare_runs(
    experiment_id: str,
    run_a: str,
    run_b: str,
    principal: Principal = Depends(require(Permission.READ)),
    session: AsyncSession = Depends(db_session),
) -> dict:
    svc = ExperimentService(session, principal.tenant_id)
    try:
        return await svc.compare_runs(run_a, run_b)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/{experiment_id}/ab-compare")
async def ab_compare(
    experiment_id: str,
    body: ABCompareRequest,
    principal: Principal = Depends(require(Permission.EVALUATE)),
    session: AsyncSession = Depends(db_session),
    engine: ScoringEngine = Depends(get_scoring_engine),
) -> dict:
    svc = ExperimentService(session, principal.tenant_id)
    try:
        return await svc.ab_compare(
            experiment_id=experiment_id,
            baseline_version=body.baseline_agent_version,
            candidate_version=body.candidate_agent_version,
            dataset_id=body.dataset_id,
            evaluator_ids=body.evaluator_ids,
            registry=engine.registry,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

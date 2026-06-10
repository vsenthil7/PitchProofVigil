"""Tests for the EvaluationService and GateService application workflows."""
from __future__ import annotations

from app.alerting.service import AlertingService
from app.core.config import Settings
from app.core.models import ConciergeRequest, Language
from app.datasets.eval_service import EvaluationService, build_trace
from app.datasets.gate_service import GateService
from app.db.models import GoldenDatasetRow
from app.evaluators.registry import build_default_registry
from app.evaluators.scoring import GatePolicy, ScoringEngine
from app.observability.metrics import Metrics
from app.orchestration.orchestrator import ConciergeOrchestrator
from app.repositories.registry import (
    AlertRepository,
    GateDecisionRepository,
    GoldenDatasetRepository,
)
from app.repositories.traces import EvaluationRepository, TraceRepository

SETTINGS = Settings(use_mocks=True)


def _engine():
    return ScoringEngine(build_default_registry(SETTINGS))


def _orch():
    return ConciergeOrchestrator(SETTINGS)


async def test_eval_service_persists_and_scores(db, tenant_id):
    engine = _engine()
    policy = GatePolicy.from_registry(engine.registry, threshold=0.7)
    async with db.session() as s:
        svc = EvaluationService(
            tenant_id, _orch(), engine,
            TraceRepository(s, tenant_id), EvaluationRepository(s, tenant_id),
            AlertingService(AlertRepository(s, tenant_id)), Metrics(),
        )
        out = await svc.ask(ConciergeRequest(text="When does Spain play Germany?"), policy)
        assert out.report.passed
        assert out.cost["calls"] == 1
    async with db.session() as s:
        assert await TraceRepository(s, tenant_id).count() == 1
        evals = await EvaluationRepository(s, tenant_id).for_trace(out.trace.trace_id)
        assert len(evals) == 15


async def test_eval_service_alerts_on_blocking(db, tenant_id):
    # Force a blocking failure via a query that produces unsafe content path is
    # hard; instead use a kickoff query with a strict tolerance won't fail here.
    # Use the orchestrator's graceful-degrade path: a fact intent with no team
    # → groundedness FAIL (blocking).
    engine = _engine()
    policy = GatePolicy.from_registry(engine.registry, threshold=0.1)
    async with db.session() as s:
        svc = EvaluationService(
            tenant_id, _orch(), engine,
            TraceRepository(s, tenant_id), EvaluationRepository(s, tenant_id),
            AlertingService(AlertRepository(s, tenant_id)), Metrics(),
        )
        await svc.ask(ConciergeRequest(text="which gate do I use"), policy)
    async with db.session() as s:
        alerts = await AlertRepository(s, tenant_id).list()
        assert len(alerts) >= 1


async def test_gate_service_inline(db, tenant_id):
    engine = _engine()
    policy = GatePolicy.from_registry(engine.registry, threshold=0.6)
    async with db.session() as s:
        svc = GateService(
            tenant_id, _orch(), engine,
            GoldenDatasetRepository(s, tenant_id),
            GateDecisionRepository(s, tenant_id), Metrics(),
        )
        decision = await svc.run_inline("v1", ["I want to buy a ticket"], policy)
        assert decision.total_traces() == 1
    async with db.session() as s:
        decisions = await GateDecisionRepository(s, tenant_id).list()
        assert len(decisions) == 1


async def test_gate_service_dataset_with_baseline(db, tenant_id):
    engine = _engine()
    policy = GatePolicy.from_registry(engine.registry, threshold=0.6)
    async with db.session() as s:
        # Seed a dataset and a prior passing decision (baseline).
        await GoldenDatasetRepository(s, tenant_id).create(
            GoldenDatasetRow(tenant_id=tenant_id, name="core", examples=[{"text": "I want to buy a ticket"}])
        )
        svc = GateService(
            tenant_id, _orch(), engine,
            GoldenDatasetRepository(s, tenant_id),
            GateDecisionRepository(s, tenant_id), Metrics(),
        )
        first = await svc.run_candidate("v1", "core", policy)
        assert first.total_traces() == 1
        # Second run now has a baseline from the first.
        second = await svc.run_candidate("v2", "core", policy)
        assert second.total_traces() == 1


async def test_gate_service_empty_dataset(db, tenant_id):
    engine = _engine()
    policy = GatePolicy.from_registry(engine.registry, threshold=0.6)
    async with db.session() as s:
        svc = GateService(
            tenant_id, _orch(), engine,
            GoldenDatasetRepository(s, tenant_id),
            GateDecisionRepository(s, tenant_id), Metrics(),
        )
        # Dataset does not exist → empty examples → zero traces.
        decision = await svc.run_candidate("v1", "missing", policy)
        assert decision.total_traces() == 0


def test_build_trace_shape():
    from app.orchestration.tools import ToolResult

    req = ConciergeRequest(text="x", language=Language.EN)
    from app.core.models import ConciergeResponse, IntentType

    resp = ConciergeResponse(
        request_id=req.request_id, text="ans", detected_intent=IntentType.TICKETING,
        language=Language.EN, model="mock-concierge",
    )
    trace = build_trace(req, resp, [ToolResult.success("ticketing_info", guidance="g")])
    assert len(trace.spans) == 2  # root + 1 tool
    assert trace.spans[0].kind.value == "AGENT"
    assert trace.spans[1].kind.value == "TOOL"

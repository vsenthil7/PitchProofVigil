"""Tests for the repository layer (tenant-scoped data access)."""
from __future__ import annotations

from app.db.models import (
    AlertChannel,
    AlertRow,
    APIKey,
    EvaluationRow,
    GateDecisionRow,
    GatePolicyRow,
    GoldenDatasetRow,
    Role,
    SpanRow,
    TraceRow,
    User,
)
from app.repositories.registry import (
    AlertRepository,
    APIKeyRepository,
    GateDecisionRepository,
    GatePolicyRepository,
    GoldenDatasetRepository,
    TenantRepository,
    UserRepository,
)
from app.repositories.traces import EvaluationRepository, TraceRepository


def _trace(tid, trace_id="t1", intent="kickoff_time"):
    return TraceRow(
        id=trace_id,
        tenant_id=tid,
        request_text="When does Spain play?",
        language="en",
        intent=intent,
        response_text="20:00",
        latency_ms=10.0,
        grounded_facts={"k": "v"},
    )


# ---- Trace repository ----

async def test_trace_add_get_list_count(db, tenant_id):
    async with db.session() as s:
        repo = TraceRepository(s, tenant_id)
        await repo.add(_trace(tenant_id), [SpanRow(trace_id="t1", tenant_id=tenant_id, name="a", kind="AGENT")])
    async with db.session() as s:
        repo = TraceRepository(s, tenant_id)
        assert await repo.count() == 1
        assert (await repo.get("t1")).intent == "kickoff_time"
        assert await repo.get("missing") is None
        assert len(await repo.list()) == 1
        assert len(await repo.get_spans("t1")) == 1
        assert await repo.count_by_intent() == {"kickoff_time": 1}


async def test_trace_tenant_isolation(db, tenant_id):
    async with db.session() as s:
        await TraceRepository(s, tenant_id).add(_trace(tenant_id), [])
    async with db.session() as s:
        other = TraceRepository(s, "other-tenant")
        assert await other.get("t1") is None
        assert await other.count() == 0


async def test_trace_count_by_intent_null(db, tenant_id):
    async with db.session() as s:
        repo = TraceRepository(s, tenant_id)
        await repo.add(_trace(tenant_id, "t2", intent=None), [])
    async with db.session() as s:
        repo = TraceRepository(s, tenant_id)
        assert "unknown" in await repo.count_by_intent()


# ---- Evaluation repository ----

async def test_evaluation_aggregations(db, tenant_id):
    async with db.session() as s:
        await TraceRepository(s, tenant_id).add(_trace(tenant_id), [])
        erepo = EvaluationRepository(s, tenant_id)
        await erepo.add_many([
            EvaluationRow(trace_id="t1", evaluator="factual_accuracy", version="2", category="correctness", verdict="pass", score=1.0, confidence=1.0, summary="ok"),
            EvaluationRow(trace_id="t1", evaluator="pii_leakage", version="1", category="safety", verdict="fail", score=0.0, confidence=1.0, summary="bad"),
            EvaluationRow(trace_id="t1", evaluator="pii_leakage", version="1", category="safety", verdict="pass", score=1.0, confidence=1.0, summary="ok"),
        ])
    async with db.session() as s:
        erepo = EvaluationRepository(s, tenant_id)
        assert len(await erepo.for_trace("t1")) == 3
        assert await erepo.verdict_breakdown() == {"pass": 2, "fail": 1}
        rates = await erepo.failure_rate_by_evaluator()
        assert rates["factual_accuracy"] == 0.0
        assert rates["pii_leakage"] == 0.5
        assert await erepo.recent_mean_score("pii_leakage") == 0.5
        assert await erepo.recent_mean_score("nonexistent") is None


# ---- Tenant / user / api key ----

async def test_tenant_repo(db):
    async with db.session() as s:
        repo = TenantRepository(s)
        t = await repo.create("Acme", "acme")
    async with db.session() as s:
        repo = TenantRepository(s)
        assert (await repo.get(t.id)).name == "Acme"
        assert (await repo.get_by_slug("acme")).id == t.id
        assert await repo.get_by_slug("nope") is None
        assert len(await repo.list()) == 1


async def test_user_repo(db, tenant_id):
    async with db.session() as s:
        repo = UserRepository(s)
        u = await repo.create(User(tenant_id=tenant_id, email="a@b.com", hashed_password="x", role=Role.ADMIN))
    async with db.session() as s:
        repo = UserRepository(s)
        assert (await repo.get(u.id)).email == "a@b.com"
        assert (await repo.get_by_email(tenant_id, "a@b.com")).id == u.id
        assert await repo.get_by_email(tenant_id, "no@b.com") is None


async def test_api_key_repo(db, tenant_id):
    async with db.session() as s:
        repo = APIKeyRepository(s)
        k = await repo.create(APIKey(tenant_id=tenant_id, name="ci", prefix="ppv_abc", hashed_secret="h", role=Role.OPERATOR))
        kid = k.id
    async with db.session() as s:
        repo = APIKeyRepository(s)
        found = await repo.get_by_prefix("ppv_abc")
        assert found is not None
        await repo.touch(found)
        assert found.last_used_at is not None
    async with db.session() as s:
        repo = APIKeyRepository(s)
        assert await repo.revoke(kid) is True
        assert await repo.revoke("missing") is False
    async with db.session() as s:
        repo = APIKeyRepository(s)
        assert await repo.get_by_prefix("ppv_abc") is None  # revoked


# ---- Gate policy / decision ----

async def test_gate_policy_versioning(db, tenant_id):
    async with db.session() as s:
        repo = GatePolicyRepository(s, tenant_id)
        r1 = await repo.upsert(GatePolicyRow(tenant_id=tenant_id, name="prod", threshold=0.8, evaluator_policies={}))
        assert r1.version == 1
    async with db.session() as s:
        repo = GatePolicyRepository(s, tenant_id)
        r2 = await repo.upsert(GatePolicyRow(tenant_id=tenant_id, name="prod", threshold=0.9, evaluator_policies={}))
        assert r2.version == 2
    async with db.session() as s:
        repo = GatePolicyRepository(s, tenant_id)
        active = await repo.get_active("prod")
        assert active.version == 2
        assert await repo.get_active("missing") is None
        assert len(await repo.list()) == 2


async def test_gate_decision_repo(db, tenant_id):
    async with db.session() as s:
        repo = GateDecisionRepository(s, tenant_id)
        await repo.add(GateDecisionRow(id="d1", tenant_id=tenant_id, candidate="v1", policy_name="prod", passed=True, aggregate_score=0.9, threshold=0.85, reason="ok", trace_count=3))
        await repo.add(GateDecisionRow(id="d2", tenant_id=tenant_id, candidate="v2", policy_name="prod", passed=False, aggregate_score=0.5, threshold=0.85, reason="blocked", trace_count=3))
    async with db.session() as s:
        repo = GateDecisionRepository(s, tenant_id)
        assert len(await repo.list()) == 2
        latest = await repo.latest_passing()
        assert latest.candidate == "v1"


async def test_gate_decision_latest_passing_none(db, tenant_id):
    async with db.session() as s:
        repo = GateDecisionRepository(s, tenant_id)
        assert await repo.latest_passing() is None


# ---- Golden dataset ----

async def test_golden_dataset_repo(db, tenant_id):
    async with db.session() as s:
        repo = GoldenDatasetRepository(s, tenant_id)
        await repo.create(GoldenDatasetRow(tenant_id=tenant_id, name="core", description="d", examples=[{"q": "hi"}]))
    async with db.session() as s:
        repo = GoldenDatasetRepository(s, tenant_id)
        got = await repo.get("core")
        assert len(got.examples) == 1
        updated = await repo.add_example("core", {"q": "bye"})
        assert len(updated.examples) == 2
        assert await repo.add_example("missing", {}) is None
        assert len(await repo.list()) == 1


# ---- Alerts ----

async def test_alert_repo(db, tenant_id):
    async with db.session() as s:
        repo = AlertRepository(s, tenant_id)
        await repo.add(AlertRow(tenant_id=tenant_id, severity="high", title="t", body="b", channel=AlertChannel.LOG, context={}))
    async with db.session() as s:
        repo = AlertRepository(s, tenant_id)
        alerts = await repo.list()
        assert len(alerts) == 1
        assert alerts[0].title == "t"

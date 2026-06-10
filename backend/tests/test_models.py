"""Tests for app.core.models."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.core.models import (
    ConciergeRequest,
    ConciergeResponse,
    DriftPoint,
    EvalResult,
    EvalVerdict,
    GateDecision,
    IntentType,
    Language,
    Span,
    SpanKind,
    Trace,
)


def test_request_defaults():
    r = ConciergeRequest(text="hi")
    assert r.language == Language.EN
    assert r.request_id
    assert r.session_id
    assert isinstance(r.created_at, datetime)


def test_span_duration_with_end():
    start = datetime.now(timezone.utc)
    span = Span(
        trace_id="t",
        name="n",
        kind=SpanKind.LLM,
        start_time=start,
        end_time=start + timedelta(milliseconds=250),
    )
    assert abs(span.duration_ms - 250.0) < 1.0


def test_span_duration_without_end():
    span = Span(trace_id="t", name="n", kind=SpanKind.AGENT)
    assert span.duration_ms == 0.0


def test_trace_holds_spans():
    req = ConciergeRequest(text="hi")
    trace = Trace(request=req)
    trace.spans.append(Span(trace_id=trace.trace_id, name="x", kind=SpanKind.TOOL))
    assert len(trace.spans) == 1


def test_eval_and_gate_models():
    er = EvalResult(
        trace_id="t",
        evaluator="e",
        verdict=EvalVerdict.PASS,
        score=1.0,
        explanation="ok",
    )
    gd = GateDecision(
        candidate="c",
        passed=True,
        aggregate_score=1.0,
        threshold=0.85,
        eval_results=[er],
    )
    assert gd.passed and gd.eval_results[0].verdict == EvalVerdict.PASS


def test_response_and_drift_models():
    resp = ConciergeResponse(
        request_id="r",
        text="t",
        detected_intent=IntentType.GENERAL,
        language=Language.FR,
    )
    assert resp.latency_ms == 0.0
    dp = DriftPoint(
        window_start=datetime.now(timezone.utc),
        window_end=datetime.now(timezone.utc),
        intent=IntentType.TRANSLATION,
        language=Language.AR,
        embedding_distance=0.1,
        sample_count=5,
    )
    assert dp.sample_count == 5


def test_audit_log_row_has_actor_ip_and_user_agent():
    from app.db.models.audit import AuditLogRow
    row = AuditLogRow(
        tenant_id="t1",
        actor="user:abc",
        actor_ip="1.2.3.4",
        actor_user_agent="Mozilla/5.0",
        action="login",
        target="user:abc",
    )
    assert row.actor_ip == "1.2.3.4"
    assert row.actor_user_agent == "Mozilla/5.0"


# ---- P3: durable-state models ----

def test_p3_experiment_models_construct():
    from app.db.models import (
        ExperimentItemResultRow,
        ExperimentRow,
        ExperimentRunRow,
    )
    exp = ExperimentRow(tenant_id="t1", name="exp1", dataset_id="ds1",
                        evaluator_ids=["correctness"])
    run = ExperimentRunRow(experiment_id=exp.id, tenant_id="t1", status="pending")
    item = ExperimentItemResultRow(run_id=run.id, tenant_id="t1",
                                   request_text="q", passed=True)
    assert exp.name == "exp1" and exp.evaluator_ids == ["correctness"]
    assert run.status == "pending"
    assert item.passed is True


def test_p3_cost_models_construct():
    from app.db.models import CostBudgetRow, CostEventRow
    b = CostBudgetRow(tenant_id="t1", month="2026-06", monthly_usd_cap=50.0)
    e = CostEventRow(tenant_id="t1", month="2026-06", model="gemini",
                     input_tokens=100, output_tokens=50, cost_usd=0.01)
    assert b.alert_threshold_pct == 0.8
    assert e.cost_usd == 0.01


def test_p3_sso_and_compliance_models_construct():
    from app.db.models import ComplianceExportJobRow, SSOConfigRow
    sso = SSOConfigRow(tenant_id="t1", idp_entity_id="idp",
                       idp_sso_url="https://idp/sso", idp_x509_cert="PEM")
    job = ComplianceExportJobRow(tenant_id="t1", date_from="2026-01-01",
                                 date_to="2026-06-30", export_types=["audit"])
    assert sso.is_active is True
    assert "email" in sso.attribute_mapping
    assert job.status == "pending"


def test_p3_alert_channel_has_pagerduty():
    from app.db.models import AlertChannel
    assert AlertChannel.PAGERDUTY.value == "pagerduty"

"""Evaluation service — the tenant-scoped application workflow.

Ties together: orchestrator (answer) → persistence (trace + spans) → scoring
engine (evaluate) → persistence (evaluations) → alerting (on blocking failure)
→ metrics. This is the unit of work the API calls for an `ask`, and the gate
service calls per golden example.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.alerting.service import AlertingService
from app.core.models import (
    ConciergeRequest,
    ConciergeResponse,
    Span,
    SpanKind,
    Trace,
)
from app.db.models import EvaluationRow, SpanRow, TraceRow
from app.evaluators.scoring import EvaluationReport, GatePolicy, ScoringEngine
from app.observability.metrics import Metrics
from app.orchestration.orchestrator import ConciergeOrchestrator
from app.repositories.traces import EvaluationRepository, TraceRepository


@dataclass
class AskOutcome:
    trace: Trace
    report: EvaluationReport
    cost: dict
    tool_calls: list[dict]


def _trace_to_row(trace: Trace, tenant_id: str) -> TraceRow:
    resp = trace.response
    return TraceRow(
        id=trace.trace_id,
        tenant_id=tenant_id,
        request_text=trace.request.text,
        language=trace.request.language.value,
        intent=resp.detected_intent.value if resp else None,
        response_text=resp.text if resp else None,
        model=resp.model if resp else None,
        latency_ms=resp.latency_ms if resp else 0.0,
        grounded_facts=resp.grounded_facts if resp else {},
    )


def _span_to_row(span: Span, tenant_id: str) -> SpanRow:
    return SpanRow(
        trace_id=span.trace_id,
        tenant_id=tenant_id,
        parent_id=span.parent_id,
        name=span.name,
        kind=span.kind.value,
        status=span.status,
        duration_ms=span.duration_ms,
        attributes=span.attributes,
        start_time=span.start_time,
    )


def build_trace(req: ConciergeRequest, resp: ConciergeResponse, tool_calls) -> Trace:
    """Build an in-memory trace (root + per-tool spans) from an orchestration."""
    trace = Trace(request=req, response=resp)
    root = Span(
        trace_id=trace.trace_id,
        name="concierge.orchestrate",
        kind=SpanKind.AGENT,
        attributes={
            "input.value": req.text,
            "output.value": resp.text,
            "intent": resp.detected_intent.value,
            "llm.model_name": resp.model,
        },
    )
    spans = [root]
    for tc in tool_calls:
        spans.append(
            Span(
                trace_id=trace.trace_id,
                parent_id=root.span_id,
                name=f"tool.{tc.tool}",
                kind=SpanKind.TOOL,
                status="OK" if tc.ok else "ERROR",
                attributes={"ok": tc.ok, "error": tc.error or "", **tc.data},
            )
        )
    trace.spans = spans
    return trace


class EvaluationService:
    """Tenant-scoped ask→evaluate→persist→alert workflow."""

    def __init__(
        self,
        tenant_id: str,
        orchestrator: ConciergeOrchestrator,
        engine: ScoringEngine,
        trace_repo: TraceRepository,
        eval_repo: EvaluationRepository,
        alerting: AlertingService,
        metrics: Metrics,
        bus=None,
    ) -> None:
        self.tenant_id = tenant_id
        self.orchestrator = orchestrator
        self.engine = engine
        self.trace_repo = trace_repo
        self.eval_repo = eval_repo
        self.alerting = alerting
        self.metrics = metrics
        self.bus = bus

    async def ask(self, req: ConciergeRequest, policy: GatePolicy) -> AskOutcome:
        result = self.orchestrator.run(req)
        resp = result.response
        trace = build_trace(req, resp, result.tool_calls)

        # Persist trace + spans.
        await self.trace_repo.add(
            _trace_to_row(trace, self.tenant_id),
            [_span_to_row(s, self.tenant_id) for s in trace.spans],
        )

        # Score and persist evaluations.
        report = self.engine.score_trace(trace, policy)
        eval_rows = [
            EvaluationRow(
                tenant_id=self.tenant_id,
                trace_id=trace.trace_id,
                evaluator=s.outcome.evaluator,
                version=s.outcome.version,
                category=s.outcome.category.value,
                verdict=s.outcome.verdict.value,
                score=s.outcome.score,
                confidence=s.outcome.confidence,
                summary=s.outcome.summary,
                findings=[
                    {
                        "code": f.code,
                        "message": f.message,
                        "severity": f.severity.value,
                        "evidence": f.evidence,
                    }
                    for f in s.outcome.findings
                ],
                duration_ms=s.outcome.duration_ms,
            )
            for s in report.scored
        ]
        await self.eval_repo.add_many(eval_rows)

        # Metrics.
        self.metrics.observe_agent(
            resp.detected_intent.value, self.orchestrator.mode, resp.latency_ms
        )
        for s in report.scored:
            self.metrics.observe_evaluation(
                s.outcome.evaluator, s.outcome.verdict.value
            )

        # Alert on blocking failures.
        blocking = report.blocking_failures()
        if blocking:
            await self.alerting.raise_alert(
                severity="high",
                title=f"Blocking eval failure on trace {trace.trace_id[:8]}",
                body="; ".join(f"{o.evaluator}: {o.summary}" for o in blocking),
                context={"trace_id": trace.trace_id, "intent": resp.detected_intent.value},
            )

        # Publish domain events (audit, webhooks, extra metrics) if a bus is wired.
        if self.bus is not None:
            from app.events.types import TraceEvaluated, blocking_failure

            await self.bus.publish(
                TraceEvaluated.make(
                    self.tenant_id,
                    trace.trace_id,
                    resp.detected_intent.value,
                    report.aggregate_score,
                    report.passed,
                )
            )
            if blocking:
                await self.bus.publish(
                    blocking_failure(
                        self.tenant_id,
                        trace.trace_id,
                        [o.evaluator for o in blocking],
                        "; ".join(o.summary for o in blocking),
                    )
                )

        return AskOutcome(
            trace=trace,
            report=report,
            cost=result.cost,
            tool_calls=[
                {"tool": tc.tool, "ok": tc.ok, "error": tc.error}
                for tc in result.tool_calls
            ],
        )

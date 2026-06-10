"""Trace/span mapping helpers.

Pure functions that translate in-memory domain objects (Trace, Span) into ORM
rows, and assemble an in-memory Trace (root agent span + per-tool spans) from an
orchestration result. Kept separate from the service so they're independently
testable and reusable by the gate service.
"""
from __future__ import annotations

from app.core.models import (
    ConciergeRequest,
    ConciergeResponse,
    Span,
    SpanKind,
    Trace,
)
from app.db.models import SpanRow, TraceRow


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

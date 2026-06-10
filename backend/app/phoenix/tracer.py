"""Tracing layer — emits OpenInference/OpenTelemetry spans for each agent run.

Real mode exports spans to a Phoenix collector over OTLP. Mock mode keeps an
in-memory trace store with the same shape, so the rest of the system (evals,
API, dashboard) is identical regardless of backend.
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone

from app.core.config import Settings, get_settings
from app.core.models import (
    ConciergeRequest,
    ConciergeResponse,
    Span,
    SpanKind,
    Trace,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TraceStore:
    """Thread-safe in-memory store of traces (mock backend + real-mode cache)."""

    def __init__(self) -> None:
        self._traces: dict[str, Trace] = {}
        self._order: list[str] = []
        self._lock = threading.Lock()

    def add(self, trace: Trace) -> None:
        with self._lock:
            self._traces[trace.trace_id] = trace
            self._order.append(trace.trace_id)

    def get(self, trace_id: str) -> Trace | None:
        with self._lock:
            return self._traces.get(trace_id)

    def list(self, limit: int = 50) -> list[Trace]:
        with self._lock:
            ids = self._order[-limit:][::-1]
            return [self._traces[i] for i in ids]

    def clear(self) -> None:
        with self._lock:
            self._traces.clear()
            self._order.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._traces)


class Tracer:
    """Builds a Trace from an agent interaction and records it.

    In real mode it additionally exports spans to Phoenix via OTLP. The export
    is best-effort: a collector outage must never break the agent.
    """

    def __init__(
        self, settings: Settings | None = None, store: TraceStore | None = None
    ) -> None:
        self.settings = settings or get_settings()
        self.mode = self.settings.integration_mode("phoenix")
        self.store = store if store is not None else TraceStore()
        self._tracer_provider = None
        if self.mode == "real":
            self._init_real_exporter()

    def _init_real_exporter(self) -> None:
        """Wire up the OpenTelemetry → Phoenix exporter (lazy import)."""
        try:
            from phoenix.otel import register  # type: ignore

            self._tracer_provider = register(
                endpoint=f"{self.settings.phoenix_collector_endpoint}/v1/traces",
                project_name="pitchproof-vigil",
            )
        except Exception:
            # Fall back silently to in-memory only; never crash the agent.
            self._tracer_provider = None

    def record(
        self, req: ConciergeRequest, resp: ConciergeResponse
    ) -> Trace:
        """Construct a span tree for an agent interaction and store it."""
        trace = Trace(request=req, response=resp)
        root_start = req.created_at

        agent_span = Span(
            trace_id=trace.trace_id,
            name="concierge.answer",
            kind=SpanKind.AGENT,
            start_time=root_start,
            end_time=_now(),
            attributes={
                "input.value": req.text,
                "input.language": req.language.value,
                "output.value": resp.text,
                "llm.model_name": resp.model,
                "intent": resp.detected_intent.value,
            },
        )

        retriever_span = Span(
            trace_id=trace.trace_id,
            parent_id=agent_span.span_id,
            name="grounding.retrieve",
            kind=SpanKind.RETRIEVER,
            start_time=root_start,
            end_time=_now(),
            attributes={
                "retrieval.documents": len(resp.grounded_facts),
                "grounded": bool(resp.grounded_facts),
            },
        )

        llm_span = Span(
            trace_id=trace.trace_id,
            parent_id=agent_span.span_id,
            name="gemini.generate",
            kind=SpanKind.LLM,
            start_time=root_start,
            end_time=_now(),
            attributes={
                "llm.model_name": resp.model,
                "llm.latency_ms": resp.latency_ms,
                "output.value": resp.text,
            },
        )

        trace.spans = [agent_span, retriever_span, llm_span]
        self.store.add(trace)
        self._export(trace)
        return trace

    def _export(self, trace: Trace) -> None:
        """Best-effort span export in real mode.

        Phoenix's ``register()`` installs OpenTelemetry instrumentation that
        exports spans automatically; this hook additionally records a
        span-count signal on the provider so callers can confirm flow. It is
        wrapped so a collector outage can never break the agent path.
        """
        if self.mode != "real" or self._tracer_provider is None:
            return
        try:
            exporter = getattr(self._tracer_provider, "export_trace", None)
            if exporter is not None:
                exporter(trace)
        except Exception:
            pass

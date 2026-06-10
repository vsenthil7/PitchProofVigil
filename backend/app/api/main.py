"""FastAPI application for PitchProof Vigil.

Routes:
  GET  /api/health           — integration modes + trace count
  POST /api/ask              — run the concierge, trace it, eval it live
  GET  /api/traces           — list recent traces (via MCP client)
  GET  /api/traces/{id}      — fetch one trace
  POST /api/gate             — run the regression gate over a candidate set
  GET  /api/drift            — current drift measurement
  WS   /api/live             — push new evaluated traces to the dashboard
"""
from __future__ import annotations

import asyncio
import contextlib

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.api.schemas import (
    AskRequest,
    AskResponse,
    DriftResponse,
    GateRequest,
    HealthResponse,
)
from app.core.context import AppContext, get_context
from app.core.models import ConciergeRequest, GateDecision, Trace


def create_app(context: AppContext | None = None) -> FastAPI:
    ctx = context or get_context()
    app = FastAPI(title="PitchProof Vigil", version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    subscribers: set[asyncio.Queue] = set()

    async def broadcast(payload: dict) -> None:
        for q in list(subscribers):
            await q.put(payload)

    @app.get("/api/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            modes=ctx.mode_report(),
            trace_count=len(ctx.store),
        )

    @app.post("/api/ask", response_model=AskResponse)
    async def ask(body: AskRequest) -> AskResponse:
        req = ConciergeRequest(text=body.text, language=body.language)
        resp = ctx.agent.answer(req)
        trace = ctx.tracer.record(req, resp)
        results = ctx.engine.evaluate_trace(trace)
        aggregate = ctx.engine.aggregate_score(results)
        await broadcast(
            {
                "type": "trace",
                "trace_id": trace.trace_id,
                "intent": resp.detected_intent.value,
                "aggregate": aggregate,
                "verdicts": [r.verdict.value for r in results],
            }
        )
        return AskResponse(
            trace=trace, eval_results=results, aggregate_score=aggregate
        )

    @app.get("/api/traces", response_model=list[Trace])
    async def list_traces(limit: int = 50) -> list[Trace]:
        return ctx.mcp.list_traces(limit=limit)

    @app.get("/api/traces/{trace_id}", response_model=Trace)
    async def get_trace(trace_id: str) -> Trace:
        trace = ctx.mcp.get_trace(trace_id)
        if trace is None:
            raise HTTPException(status_code=404, detail="trace not found")
        return trace

    @app.post("/api/gate", response_model=GateDecision)
    async def run_gate(body: GateRequest) -> GateDecision:
        traces: list[Trace] = []
        for q in body.queries:
            req = ConciergeRequest(text=q, language=body.language)
            resp = ctx.agent.answer(req)
            traces.append(ctx.tracer.record(req, resp))
        decision = ctx.gate.evaluate_candidate(body.candidate, traces)
        await broadcast(
            {
                "type": "gate",
                "candidate": decision.candidate,
                "passed": decision.passed,
                "aggregate": decision.aggregate_score,
            }
        )
        return decision

    @app.get("/api/drift", response_model=DriftResponse)
    async def drift() -> DriftResponse:
        traces = ctx.store.list(limit=100)
        point = ctx.drift.compute(traces)
        return DriftResponse(point=point, alerting=ctx.drift.is_alerting(point))

    @app.websocket("/api/live")
    async def live(ws: WebSocket) -> None:
        await ws.accept()
        queue: asyncio.Queue = asyncio.Queue()
        subscribers.add(queue)
        try:
            while True:
                payload = await queue.get()
                await ws.send_json(payload)
        except WebSocketDisconnect:  # pragma: no cover - network event
            pass
        finally:
            subscribers.discard(queue)

    app.state.context = ctx
    app.state.broadcast = broadcast
    app.state.subscribers = subscribers
    return app


app = create_app()

"""Enterprise application factory.

Assembles the FastAPI app with all routers, shared singletons on app.state, a
request-timing + logging middleware, and a lifespan that creates the database
schema (for dev/test; production uses Alembic).
"""
from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers_auth import router as auth_router
from app.api.routers_eval import router as eval_router
from app.api.routers_gate import (
    admin_router,
    dataset_router,
    gate_router,
    policy_router,
)
from app.core.config import Settings, get_settings
from app.db.engine import Database
from app.evaluators.registry import build_default_registry
from app.evaluators.scoring import ScoringEngine
from app.observability.logging import (
    bind_request_context,
    clear_request_context,
    configure_logging,
    get_logger,
)
from app.observability.metrics import Metrics
from app.orchestration.orchestrator import ConciergeOrchestrator


def create_app(
    settings: Settings | None = None,
    database: Database | None = None,
    create_schema: bool = True,
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(json_logs=True)
    log = get_logger("api")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if create_schema:
            await app.state.database.create_all()
        log.info("startup", dsn=app.state.database.dsn)
        yield
        await app.state.database.dispose()
        log.info("shutdown")

    app = FastAPI(title="PitchProof Vigil", version="2.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Shared singletons.
    registry = build_default_registry(settings)
    app.state.settings = settings
    app.state.database = database or Database(settings)
    app.state.evaluator_registry = registry
    app.state.scoring_engine = ScoringEngine(registry)
    app.state.orchestrator = ConciergeOrchestrator(settings)
    app.state.metrics = Metrics()

    @app.middleware("http")
    async def observe(request: Request, call_next):
        start = time.perf_counter()
        bind_request_context(path=request.url.path, method=request.method)
        try:
            response = await call_next(request)
        finally:
            clear_request_context()
        duration = time.perf_counter() - start
        app.state.metrics.observe_http(
            request.method, request.url.path, getattr(response, "status_code", 500), duration
        )
        return response

    app.include_router(auth_router)
    app.include_router(eval_router)
    app.include_router(gate_router)
    app.include_router(policy_router)
    app.include_router(dataset_router)
    app.include_router(admin_router)
    return app


app = create_app()

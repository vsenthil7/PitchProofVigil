"""FastAPI dependencies: DB sessions, authentication, and service assembly.

A request authenticates via a Bearer JWT or an `X-API-Key` header, yielding a
``Principal``. All downstream repositories/services are constructed scoped to
``principal.tenant_id`` so tenant isolation is automatic. Singletons (engine,
evaluator registry, scoring engine, orchestrator, metrics) live on app.state.
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import decode_access_token
from app.auth.service import AuthError, AuthService, Permission, Principal, require_permission
from app.core.config import Settings
from app.db.engine import Database
from app.evaluators.scoring import GatePolicy, ScoringEngine


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


def get_db(request: Request) -> Database:
    return request.app.state.database


def get_scoring_engine(request: Request) -> ScoringEngine:
    return request.app.state.scoring_engine


def get_orchestrator(request: Request):
    return request.app.state.orchestrator


def get_metrics_dep(request: Request):
    return request.app.state.metrics


def get_cipher(request: Request):
    return request.app.state.cipher


async def db_session(db: Database = Depends(get_db)) -> AsyncIterator[AsyncSession]:
    async with db.session() as session:
        yield session


async def get_principal(
    request: Request,
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
    session: AsyncSession = Depends(db_session),
    settings: Settings = Depends(get_settings_dep),
) -> Principal:
    """Resolve the caller from a Bearer JWT or an API key header."""
    auth = AuthService(session, settings)
    try:
        if x_api_key:
            return await auth.principal_from_api_key(x_api_key)
        if authorization and authorization.lower().startswith("bearer "):
            token = authorization[7:]
            claims = decode_access_token(token, settings)
            if claims is None:
                raise AuthError("Invalid or expired token.")
            return auth.principal_from_token(claims)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    raise HTTPException(status_code=401, detail="Authentication required.")


def require(permission: Permission):
    """Dependency factory enforcing a permission on the resolved principal."""

    async def _dep(principal: Principal = Depends(get_principal)) -> Principal:
        try:
            require_permission(principal, permission)
        except AuthError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.message)
        return principal

    return _dep


async def active_policy(
    request: Request,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(db_session),
    engine: ScoringEngine = Depends(get_scoring_engine),
) -> GatePolicy:
    """Load the tenant's active 'production' policy, or a default from registry."""
    from app.db.models import GatePolicyRow  # local import to avoid cycle
    from app.repositories.registry import GatePolicyRepository

    repo = GatePolicyRepository(session, principal.tenant_id)
    row: GatePolicyRow | None = await repo.get_active("production")
    if row is None:
        return GatePolicy.from_registry(engine.registry, name="default")
    from app.evaluators.scoring import EvaluatorPolicy

    policies = {
        name: EvaluatorPolicy(name=name, **cfg)
        for name, cfg in row.evaluator_policies.items()
    }
    return GatePolicy(
        name=row.name,
        threshold=row.threshold,
        evaluator_policies=policies,
        fail_on_any_blocking=row.fail_on_any_blocking,
    )

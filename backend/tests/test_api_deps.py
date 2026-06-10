"""Direct unit tests for API dependency functions.

These call the dependency callables directly (not only through TestClient) so
coverage is reliably credited for async sub-dependencies and error branches.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.api import deps
from app.auth.security import create_access_token
from app.auth.service import AuthService, Permission, Principal
from app.core.config import Settings
from app.db.models import GatePolicyRow, Role
from app.evaluators.registry import build_default_registry
from app.evaluators.scoring import ScoringEngine
from app.repositories.registry import GatePolicyRepository

SETTINGS = Settings(jwt_secret="test-secret", use_mocks=True)


class _FakeState:
    pass


class _FakeApp:
    def __init__(self, **kw):
        self.state = _FakeState()
        for k, v in kw.items():
            setattr(self.state, k, v)


class _FakeRequest:
    def __init__(self, app):
        self.app = app


def _engine():
    return ScoringEngine(build_default_registry(SETTINGS))


def test_state_accessors():
    engine = _engine()
    app = _FakeApp(
        settings=SETTINGS, database="DB", scoring_engine=engine,
        orchestrator="ORCH", metrics="M",
    )
    req = _FakeRequest(app)
    assert deps.get_settings_dep(req) is SETTINGS
    assert deps.get_db(req) == "DB"
    assert deps.get_scoring_engine(req) is engine
    assert deps.get_orchestrator(req) == "ORCH"
    assert deps.get_metrics_dep(req) == "M"


async def test_get_principal_via_api_key(db, tenant_id):
    async with db.session() as s:
        auth = AuthService(s, SETTINGS)
        full, _ = await auth.create_api_key(tenant_id, "k", Role.OPERATOR)
    async with db.session() as s:
        p = await deps.get_principal(
            request=None, authorization=None, x_api_key=full, session=s, settings=SETTINGS
        )
        assert p.kind == "api_key"
        assert p.tenant_id == tenant_id


async def test_get_principal_via_bearer(db, tenant_id):
    token = create_access_token("u1", tenant_id, "admin", SETTINGS)
    async with db.session() as s:
        p = await deps.get_principal(
            request=None, authorization=f"Bearer {token}", x_api_key=None,
            session=s, settings=SETTINGS,
        )
        assert p.kind == "user"
        assert p.role == Role.ADMIN


async def test_get_principal_bad_token(db):
    async with db.session() as s:
        with pytest.raises(HTTPException) as ei:
            await deps.get_principal(
                request=None, authorization="Bearer garbage", x_api_key=None,
                session=s, settings=SETTINGS,
            )
        assert ei.value.status_code == 401


async def test_get_principal_no_credentials(db):
    async with db.session() as s:
        with pytest.raises(HTTPException) as ei:
            await deps.get_principal(
                request=None, authorization=None, x_api_key=None,
                session=s, settings=SETTINGS,
            )
        assert ei.value.status_code == 401


async def test_get_principal_bad_api_key(db):
    async with db.session() as s:
        with pytest.raises(HTTPException) as ei:
            await deps.get_principal(
                request=None, authorization=None, x_api_key="malformed",
                session=s, settings=SETTINGS,
            )
        assert ei.value.status_code == 401


async def test_require_permission_dep_allows_and_denies():
    allow = deps.require(Permission.READ)
    viewer = Principal(subject="u", tenant_id="t", role=Role.VIEWER, kind="user")
    assert await allow(principal=viewer) is viewer

    deny = deps.require(Permission.WRITE)
    with pytest.raises(HTTPException) as ei:
        await deny(principal=viewer)
    assert ei.value.status_code == 403


async def test_active_policy_default_when_none(db, tenant_id):
    engine = _engine()
    principal = Principal(subject="u", tenant_id=tenant_id, role=Role.OWNER, kind="user")
    async with db.session() as s:
        policy = await deps.active_policy(
            request=None, principal=principal, session=s, engine=engine
        )
        assert policy.name == "default"
        assert len(policy.evaluator_policies) == len(engine.registry)


async def test_active_policy_loads_custom(db, tenant_id):
    engine = _engine()
    principal = Principal(subject="u", tenant_id=tenant_id, role=Role.OWNER, kind="user")
    async with db.session() as s:
        await GatePolicyRepository(s, tenant_id).upsert(
            GatePolicyRow(
                tenant_id=tenant_id,
                name="production",
                threshold=0.77,
                fail_on_any_blocking=False,
                evaluator_policies={
                    "latency_slo": {"enabled": True, "weight": 3.0, "blocking": False, "config": {"budget_ms": 5000}},
                },
            )
        )
    async with db.session() as s:
        policy = await deps.active_policy(
            request=None, principal=principal, session=s, engine=engine
        )
        assert policy.name == "production"
        assert policy.threshold == 0.77
        assert policy.fail_on_any_blocking is False
        assert policy.evaluator_policies["latency_slo"].weight == 3.0

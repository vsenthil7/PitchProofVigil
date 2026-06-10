"""SQLModel database schema for PitchProof Vigil.

Multi-tenant from the ground up: every domain row carries a tenant_id. The
schema persists the agent's traces and spans, every evaluation outcome, gate
policies and their decisions, golden datasets for the gate, and the alert log.
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Column, Index, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.sqlite import JSON as SQLITE_JSON
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


def _uuid() -> str:
    return uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


# JSON column type that works on both Postgres and SQLite.
JSONType = JSON().with_variant(SQLITE_JSON(), "sqlite")


class Role(str, enum.Enum):
    OWNER = "owner"
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class AlertChannel(str, enum.Enum):
    LOG = "log"
    WEBHOOK = "webhook"
    SLACK = "slack"


# --------------------------------------------------------------------------
# Tenancy & identity
# --------------------------------------------------------------------------


class Tenant(SQLModel, table=True):
    __tablename__ = "tenants"

    id: str = Field(default_factory=_uuid, primary_key=True)
    name: str = Field(index=True)
    slug: str = Field(sa_column_kwargs={"unique": True})
    created_at: datetime = Field(default_factory=_now)
    is_active: bool = Field(default=True)


class User(SQLModel, table=True):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("tenant_id", "email", name="uq_user_email"),)

    id: str = Field(default_factory=_uuid, primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    email: str = Field(index=True)
    hashed_password: str
    role: Role = Field(sa_column=Column(SAEnum(Role)))
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=_now)



class APIKey(SQLModel, table=True):
    __tablename__ = "api_keys"

    id: str = Field(default_factory=_uuid, primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    name: str
    prefix: str = Field(index=True)
    hashed_secret: str
    role: Role = Field(sa_column=Column(SAEnum(Role)))
    created_at: datetime = Field(default_factory=_now)
    last_used_at: datetime | None = Field(default=None)
    revoked: bool = Field(default=False)


# --------------------------------------------------------------------------
# Traces & spans
# --------------------------------------------------------------------------


class TraceRow(SQLModel, table=True):
    __tablename__ = "traces"
    __table_args__ = (
        Index("ix_traces_tenant_created", "tenant_id", "created_at"),
    )

    id: str = Field(primary_key=True)  # trace_id
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    request_text: str
    language: str
    intent: str | None = Field(default=None, index=True)
    response_text: str | None = Field(default=None)
    model: str | None = Field(default=None)
    latency_ms: float = Field(default=0.0)
    grounded_facts: dict = Field(default_factory=dict, sa_column=Column(JSONType))
    created_at: datetime = Field(default_factory=_now, index=True)



class SpanRow(SQLModel, table=True):
    __tablename__ = "spans"

    id: str = Field(default_factory=_uuid, primary_key=True)
    trace_id: str = Field(foreign_key="traces.id", index=True)
    tenant_id: str = Field(index=True)
    parent_id: str | None = Field(default=None)
    name: str
    kind: str
    status: str = Field(default="OK")
    duration_ms: float = Field(default=0.0)
    attributes: dict = Field(default_factory=dict, sa_column=Column(JSONType))
    start_time: datetime = Field(default_factory=_now)



# --------------------------------------------------------------------------
# Evaluations
# --------------------------------------------------------------------------


class EvaluationRow(SQLModel, table=True):
    __tablename__ = "evaluations"
    __table_args__ = (
        Index("ix_eval_tenant_evaluator", "tenant_id", "evaluator"),
    )

    id: str = Field(default_factory=_uuid, primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    trace_id: str = Field(foreign_key="traces.id", index=True)
    evaluator: str = Field(index=True)
    version: str
    category: str
    verdict: str = Field(index=True)
    score: float
    confidence: float
    summary: str
    findings: list = Field(default_factory=list, sa_column=Column(JSONType))
    duration_ms: float = Field(default=0.0)
    created_at: datetime = Field(default_factory=_now, index=True)


# --------------------------------------------------------------------------
# Gate policies, decisions, golden datasets
# --------------------------------------------------------------------------


class GatePolicyRow(SQLModel, table=True):
    __tablename__ = "gate_policies"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", "version", name="uq_policy_name_ver"),
    )

    id: str = Field(default_factory=_uuid, primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    name: str = Field(index=True)
    version: int = Field(default=1)
    threshold: float = Field(default=0.85)
    fail_on_any_blocking: bool = Field(default=True)
    evaluator_policies: dict = Field(default_factory=dict, sa_column=Column(JSONType))
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=_now)


class GateDecisionRow(SQLModel, table=True):
    __tablename__ = "gate_decisions"
    __table_args__ = (
        Index("ix_decision_tenant_created", "tenant_id", "created_at"),
    )

    id: str = Field(primary_key=True)  # decision_id
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    candidate: str = Field(index=True)
    policy_name: str
    passed: bool = Field(index=True)
    aggregate_score: float
    threshold: float
    category_scores: dict = Field(default_factory=dict, sa_column=Column(JSONType))
    baseline_deltas: dict = Field(default_factory=dict, sa_column=Column(JSONType))
    regressions: list = Field(default_factory=list, sa_column=Column(JSONType))
    reason: str
    trace_count: int = Field(default=0)
    created_at: datetime = Field(default_factory=_now, index=True)


class GoldenDatasetRow(SQLModel, table=True):
    __tablename__ = "golden_datasets"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_golden_name"),
    )

    id: str = Field(default_factory=_uuid, primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    name: str = Field(index=True)
    description: str = Field(default="")
    examples: list = Field(default_factory=list, sa_column=Column(JSONType))
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class AlertRow(SQLModel, table=True):
    __tablename__ = "alerts"
    __table_args__ = (
        Index("ix_alert_tenant_created", "tenant_id", "created_at"),
    )

    id: str = Field(default_factory=_uuid, primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    severity: str = Field(index=True)
    title: str
    body: str
    channel: AlertChannel = Field(sa_column=Column(SAEnum(AlertChannel)))
    context: dict = Field(default_factory=dict, sa_column=Column(JSONType))
    delivered: bool = Field(default=False)
    created_at: datetime = Field(default_factory=_now, index=True)

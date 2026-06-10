"""Governance tables: gate policies, gate decisions, golden datasets."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, Index, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.db.models._base import JSONType, utcnow, uuid_str


class GatePolicyRow(SQLModel, table=True):
    __tablename__ = "gate_policies"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", "version", name="uq_policy_name_ver"),
    )

    id: str = Field(default_factory=uuid_str, primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    name: str = Field(index=True)
    version: int = Field(default=1)
    threshold: float = Field(default=0.85)
    fail_on_any_blocking: bool = Field(default=True)
    evaluator_policies: dict = Field(default_factory=dict, sa_column=Column(JSONType))
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=utcnow)


class GateDecisionRow(SQLModel, table=True):
    __tablename__ = "gate_decisions"
    __table_args__ = (
        Index("ix_decision_tenant_created", "tenant_id", "created_at"),
    )

    id: str = Field(primary_key=True)
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
    created_at: datetime = Field(default_factory=utcnow, index=True)


class GoldenDatasetRow(SQLModel, table=True):
    __tablename__ = "golden_datasets"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_golden_name"),)

    id: str = Field(default_factory=uuid_str, primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    name: str = Field(index=True)
    description: str = Field(default="")
    examples: list = Field(default_factory=list, sa_column=Column(JSONType))
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class CostBudgetRow(SQLModel, table=True):
    """Per-tenant monthly LLM cost cap for the eval judge."""

    __tablename__ = "cost_budgets"
    __table_args__ = (
        UniqueConstraint("tenant_id", "month", name="uq_cost_budget_tenant_month"),
    )

    id: str = Field(default_factory=uuid_str, primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    monthly_usd_cap: float = Field(default=100.0)
    alert_threshold_pct: float = Field(default=0.8)  # alert at 80% of cap
    month: str = Field(index=True)  # "YYYY-MM"
    created_at: datetime = Field(default_factory=utcnow)


class CostEventRow(SQLModel, table=True):
    """One LLM call cost event, for per-tenant spend aggregation."""

    __tablename__ = "cost_events"
    __table_args__ = (Index("ix_cost_tenant_month", "tenant_id", "month"),)

    id: str = Field(default_factory=uuid_str, primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    month: str = Field(index=True)  # "YYYY-MM"
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    created_at: datetime = Field(default_factory=utcnow)

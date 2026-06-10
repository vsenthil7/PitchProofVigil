"""Experiment management tables: experiments, runs, per-item results."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, Index
from sqlmodel import Field, SQLModel

from app.db.models._base import JSONType, utcnow, uuid_str


class ExperimentRow(SQLModel, table=True):
    """A named experiment over a golden dataset with a set of evaluators."""

    __tablename__ = "experiments"
    __table_args__ = (Index("ix_exp_tenant_created", "tenant_id", "created_at"),)

    id: str = Field(default_factory=uuid_str, primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    name: str = Field(index=True)
    description: str = Field(default="")
    dataset_id: str = Field(foreign_key="golden_datasets.id", index=True)
    evaluator_ids: list = Field(default_factory=list, sa_column=Column(JSONType))
    created_at: datetime = Field(default_factory=utcnow)
    last_run_at: datetime | None = Field(default=None)


class ExperimentRunRow(SQLModel, table=True):
    """One execution of an experiment (over the full dataset)."""

    __tablename__ = "experiment_runs"
    __table_args__ = (Index("ix_exprun_exp_created", "experiment_id", "created_at"),)

    id: str = Field(default_factory=uuid_str, primary_key=True)
    experiment_id: str = Field(foreign_key="experiments.id", index=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    status: str = Field(default="pending", index=True)  # pending|running|complete|error
    aggregate_score: float | None = Field(default=None)
    verdict_summary: dict = Field(default_factory=dict, sa_column=Column(JSONType))
    # winner for A/B comparisons
    ab_baseline_version: str | None = Field(default=None)
    ab_candidate_version: str | None = Field(default=None)
    ab_winner: str | None = Field(default=None)
    ab_delta_score: float | None = Field(default=None)
    ab_cohens_d: float | None = Field(default=None)
    created_at: datetime = Field(default_factory=utcnow)
    completed_at: datetime | None = Field(default=None)


class ExperimentItemResultRow(SQLModel, table=True):
    """Per-item evaluation result within an experiment run."""

    __tablename__ = "experiment_item_results"
    __table_args__ = (Index("ix_expitem_run", "run_id"),)

    id: str = Field(default_factory=uuid_str, primary_key=True)
    run_id: str = Field(foreign_key="experiment_runs.id", index=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    example_index: int = Field(default=0)
    request_text: str
    response_text: str | None = Field(default=None)
    verdicts: dict = Field(default_factory=dict, sa_column=Column(JSONType))
    aggregate_score: float | None = Field(default=None)
    passed: bool = Field(default=False)
    created_at: datetime = Field(default_factory=utcnow)

"""Evaluation results table."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, Index
from sqlmodel import Field, SQLModel

from app.db.models._base import JSONType, utcnow, uuid_str


class EvaluationRow(SQLModel, table=True):
    __tablename__ = "evaluations"
    __table_args__ = (Index("ix_eval_tenant_evaluator", "tenant_id", "evaluator"),)

    id: str = Field(default_factory=uuid_str, primary_key=True)
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
    created_at: datetime = Field(default_factory=utcnow, index=True)

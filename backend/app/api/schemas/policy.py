"""Policy & evaluator API schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field


class EvaluatorPolicyIn(BaseModel):
    enabled: bool = True
    weight: float | None = None
    blocking: bool | None = None
    config: dict = Field(default_factory=dict)


class PolicyUpsertRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    threshold: float = Field(ge=0.0, le=1.0, default=0.85)
    fail_on_any_blocking: bool = True
    evaluator_policies: dict[str, EvaluatorPolicyIn] = Field(default_factory=dict)


class PolicyResponse(BaseModel):
    id: str
    name: str
    version: int
    threshold: float
    fail_on_any_blocking: bool
    evaluator_policies: dict
    is_active: bool


class EvaluatorSpecOut(BaseModel):
    name: str
    version: str
    category: str
    title: str
    description: str
    default_weight: float
    blocking_by_default: bool

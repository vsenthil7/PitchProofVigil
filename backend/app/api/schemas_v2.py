"""API request/response schemas for the enterprise endpoints."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.core.models import Language
from app.db.models import Role


# ---- Auth ----


class RegisterRequest(BaseModel):
    tenant_name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9-]+$")
    owner_email: str = Field(min_length=3, max_length=200)
    owner_password: str = Field(min_length=8, max_length=200)


class RegisterResponse(BaseModel):
    tenant_id: str
    owner_id: str


class LoginRequest(BaseModel):
    tenant_id: str
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CreateUserRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)
    role: Role


class CreateAPIKeyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    role: Role


class APIKeyResponse(BaseModel):
    id: str
    name: str
    prefix: str
    role: Role
    api_key: str  # full key, shown once


# ---- Ask / evaluate ----


class AskRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    language: Language = Language.EN


class FindingOut(BaseModel):
    code: str
    message: str
    severity: str
    evidence: dict


class EvalOut(BaseModel):
    evaluator: str
    category: str
    verdict: str
    score: float
    confidence: float
    summary: str
    findings: list[FindingOut]
    duration_ms: float


class AskResponse(BaseModel):
    trace_id: str
    answer: str
    intent: str
    model: str
    latency_ms: float
    aggregate_score: float
    passed: bool
    reason: str
    category_scores: dict[str, float]
    evaluations: list[EvalOut]
    cost: dict
    tool_calls: list[dict]


# ---- Gate ----


class GateRequest(BaseModel):
    candidate: str = Field(min_length=1, max_length=200)
    queries: list[str] = Field(min_length=1, max_length=200)
    language: Language = Language.EN


class GateDatasetRequest(BaseModel):
    candidate: str = Field(min_length=1, max_length=200)
    dataset: str = Field(min_length=1, max_length=200)


class GateResponse(BaseModel):
    decision_id: str
    candidate: str
    passed: bool
    aggregate_score: float
    threshold: float
    category_scores: dict[str, float]
    baseline_deltas: dict[str, float]
    regressions: list[str]
    reason: str
    trace_count: int


# ---- Policies ----


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


# ---- Datasets ----


class CreateDatasetRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    examples: list[dict] = Field(default_factory=list)


class DatasetResponse(BaseModel):
    id: str
    name: str
    description: str
    example_count: int

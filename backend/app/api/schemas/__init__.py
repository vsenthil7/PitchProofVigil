"""API schema package — re-exports every schema for ergonomic imports.

Schemas are organized by domain (auth, evaluation, gate, policy, dataset) but
callers can import any of them from ``app.api.schemas`` directly.
"""
from app.api.schemas.auth import (
    APIKeyResponse,
    CreateAPIKeyRequest,
    CreateUserRequest,
    LoginRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
)
from app.api.schemas.dataset import CreateDatasetRequest, DatasetResponse
from app.api.schemas.evaluation import (
    AskRequest,
    AskResponse,
    EvalOut,
    FindingOut,
)
from app.api.schemas.gate import GateDatasetRequest, GateRequest, GateResponse
from app.api.schemas.policy import (
    EvaluatorPolicyIn,
    EvaluatorSpecOut,
    PolicyResponse,
    PolicyUpsertRequest,
)

__all__ = [
    "APIKeyResponse",
    "CreateAPIKeyRequest",
    "CreateUserRequest",
    "LoginRequest",
    "RegisterRequest",
    "RegisterResponse",
    "TokenResponse",
    "CreateDatasetRequest",
    "DatasetResponse",
    "AskRequest",
    "AskResponse",
    "EvalOut",
    "FindingOut",
    "GateDatasetRequest",
    "GateRequest",
    "GateResponse",
    "EvaluatorPolicyIn",
    "EvaluatorSpecOut",
    "PolicyResponse",
    "PolicyUpsertRequest",
]

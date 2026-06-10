"""Backward-compatible re-export of the repository aggregates.

Repositories now live in focused modules (identity, governance, alerts, traces,
audit). This module re-exports them so existing imports keep working.
"""
from app.repositories.alerts import AlertRepository
from app.repositories.governance import (
    GateDecisionRepository,
    GatePolicyRepository,
    GoldenDatasetRepository,
)
from app.repositories.identity import (
    APIKeyRepository,
    TenantRepository,
    UserRepository,
)

__all__ = [
    "AlertRepository",
    "GateDecisionRepository",
    "GatePolicyRepository",
    "GoldenDatasetRepository",
    "APIKeyRepository",
    "TenantRepository",
    "UserRepository",
]

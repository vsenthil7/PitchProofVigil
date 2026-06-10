"""Database models package.

Organized by aggregate (identity, tracing, evaluation, governance, ops) with
shared primitives in ``_base``. Everything is re-exported here so existing
imports of ``app.db.models`` keep working unchanged.
"""
from app.db.models._base import (
    AlertChannel,
    JSONType,
    Role,
    utcnow,
    uuid_str,
)
from app.db.models.audit import AuditLogRow
from app.db.models.evaluation import EvaluationRow
from app.db.models.governance import (
    GateDecisionRow,
    GatePolicyRow,
    GoldenDatasetRow,
)
from app.db.models.identity import APIKey, Tenant, User
from app.db.models.ops import AlertRow
from app.db.models.tracing import SpanRow, TraceRow
from app.db.models.webhooks import WebhookSubscriptionRow

__all__ = [
    "AlertChannel",
    "JSONType",
    "Role",
    "utcnow",
    "uuid_str",
    "AuditLogRow",
    "EvaluationRow",
    "GateDecisionRow",
    "GatePolicyRow",
    "GoldenDatasetRow",
    "APIKey",
    "Tenant",
    "User",
    "AlertRow",
    "SpanRow",
    "TraceRow",
    "WebhookSubscriptionRow",
]

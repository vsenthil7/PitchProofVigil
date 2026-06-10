"""Shared model primitives: id/timestamp helpers, enums, portable JSON type."""
from __future__ import annotations

import enum
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.dialects.sqlite import JSON as SQLITE_JSON
from sqlalchemy.types import JSON


def uuid_str() -> str:
    return uuid4().hex


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# JSON column type portable across Postgres and SQLite.
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
    PAGERDUTY = "pagerduty"

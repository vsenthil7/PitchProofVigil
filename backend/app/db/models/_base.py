"""Shared model primitives: id/timestamp helpers, enums, portable JSON type."""
from __future__ import annotations

import enum
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.dialects.sqlite import JSON as SQLITE_JSON
from sqlalchemy.types import JSON
from sqlalchemy.types import DateTime, TypeDecorator


def uuid_str() -> str:
    return uuid4().hex


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# Timezone-aware UTC datetime, portable across Postgres and SQLite. Postgres
# stores TIMESTAMP WITH TIME ZONE; SQLite has no tz type, so we normalise on
# the way in/out. Values are always returned as aware UTC. This avoids the
# "cant subtract offset-naive and offset-aware" error asyncpg raises when an
# aware datetime is bound to a naive (TIMESTAMP WITHOUT TIME ZONE) column.
class AwareDateTime(TypeDecorator):
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


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

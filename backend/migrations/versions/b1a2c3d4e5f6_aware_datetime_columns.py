"""Convert all naive timestamp columns to TIMESTAMP WITH TIME ZONE.

The models always produce timezone-aware UTC datetimes (utcnow), but the columns
were created as TIMESTAMP WITHOUT TIME ZONE. SQLite tolerated this; Postgres
(asyncpg) rejects binding an aware datetime to a naive column with
"can't subtract offset-naive and offset-aware datetimes". This migration alters
every timestamp column in the schema to WITH TIME ZONE, interpreting existing
naive values as UTC. No-op on SQLite (no distinct tz timestamp type).

Revision ID: b1a2c3d4e5f6
Revises: 9f78e1548d36
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "b1a2c3d4e5f6"
down_revision = "9f78e1548d36"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return  # SQLite has no separate tz-aware timestamp type
    rows = bind.execute(
        sa.text(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE table_schema = current_schema() "
            "AND data_type = 'timestamp without time zone'"
        )
    ).fetchall()
    for table_name, column_name in rows:
        op.execute(
            sa.text(
                f'ALTER TABLE "{table_name}" ALTER COLUMN "{column_name}" '
                f'TYPE TIMESTAMP WITH TIME ZONE '
                f'USING "{column_name}" AT TIME ZONE ''UTC'''
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    rows = bind.execute(
        sa.text(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE table_schema = current_schema() "
            "AND data_type = 'timestamp with time zone'"
        )
    ).fetchall()
    for table_name, column_name in rows:
        op.execute(
            sa.text(
                f'ALTER TABLE "{table_name}" ALTER COLUMN "{column_name}" '
                f'TYPE TIMESTAMP WITHOUT TIME ZONE '
                f'USING "{column_name}" AT TIME ZONE ''UTC'''
            )
        )

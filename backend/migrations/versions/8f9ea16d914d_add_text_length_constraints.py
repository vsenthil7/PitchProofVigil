"""add_text_length_constraints

Cap trace text columns at explicit VARCHAR lengths (request_text 4096,
response_text 16384). On PostgreSQL this enforces the bound at the DB; on
SQLite VARCHAR length is advisory, so the batch op is a safe no-op there.
Nullability is unchanged (request_text NOT NULL, response_text NULL).

Revision ID: 8f9ea16d914d
Revises: 8f82936c9ea9
Create Date: 2026-06-03 17:56:01.436173
"""
from alembic import op
import sqlalchemy as sa


revision = "8f9ea16d914d"
down_revision = "8f82936c9ea9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("traces") as batch:
        batch.alter_column(
            "request_text",
            existing_type=sa.String(),
            type_=sa.String(length=4096),
            existing_nullable=False,
        )
        batch.alter_column(
            "response_text",
            existing_type=sa.String(),
            type_=sa.String(length=16384),
            existing_nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("traces") as batch:
        batch.alter_column(
            "request_text",
            existing_type=sa.String(length=4096),
            type_=sa.String(),
            existing_nullable=False,
        )
        batch.alter_column(
            "response_text",
            existing_type=sa.String(length=16384),
            type_=sa.String(),
            existing_nullable=True,
        )

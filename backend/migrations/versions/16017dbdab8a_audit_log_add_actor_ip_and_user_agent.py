"""audit_log_add_actor_ip_and_user_agent

Adds nullable actor_ip and actor_user_agent columns to the audit_log table so
audit entries can record the network origin of an actor. Both nullable; no
backfill needed. SQLite-safe (add_column only).

Revision ID: 16017dbdab8a
Revises: 8f9ea16d914d
Create Date: 2026-06-03 17:58:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "16017dbdab8a"
down_revision = "8f9ea16d914d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("audit_log", sa.Column("actor_ip", sa.String(), nullable=True))
    op.add_column(
        "audit_log", sa.Column("actor_user_agent", sa.String(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("audit_log", "actor_user_agent")
    op.drop_column("audit_log", "actor_ip")

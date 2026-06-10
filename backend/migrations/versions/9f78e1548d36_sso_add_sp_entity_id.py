"""sso_add_sp_entity_id

Adds the sp_entity_id column to sso_configs (the SP metadata entityID generated
per tenant during IdP configuration). Non-null with a server default of '' so
existing rows backfill cleanly. SQLite-safe (add_column only).

Revision ID: 9f78e1548d36
Revises: a3c69850b278
Create Date: 2026-06-04 06:40:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "9f78e1548d36"
down_revision = "a3c69850b278"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sso_configs",
        sa.Column("sp_entity_id", sa.String(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("sso_configs", "sp_entity_id")

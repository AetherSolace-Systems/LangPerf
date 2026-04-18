"""workspace_settings — jsonb kv store for UI-managed config

Single-row-per-key table storing configuration that the Settings UI mutates
at runtime (log forwarding config, later: integrations, SDK keys, etc.).
Simpler than a strongly-typed column per setting, and avoids frequent
migrations as new sections appear.

Revision ID: 0008
Revises: 0007
Create Date: 2026-04-17 00:07:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspace_settings",
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("value", JSONB(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("workspace_settings")

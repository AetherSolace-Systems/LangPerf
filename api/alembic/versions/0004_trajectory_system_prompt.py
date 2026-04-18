"""trajectories.system_prompt

Stores the system prompt extracted from the first LLM span of each
trajectory. Populated lazily during ingest; old rows stay NULL until they
are re-ingested or have a matching span reprocessed.

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-17 00:03:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "trajectories",
        sa.Column("system_prompt", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("trajectories", "system_prompt")

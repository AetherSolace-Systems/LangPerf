"""trajectories.input_tokens + output_tokens

Split token_count into input/output so the dashboard + agent-detail cost
charts can render real proportions instead of the prior 80/20 assumption.
Both default to 0 (non-null) to match the existing token_count shape.

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-17 00:05:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "trajectories",
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "trajectories",
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("trajectories", "output_tokens")
    op.drop_column("trajectories", "input_tokens")

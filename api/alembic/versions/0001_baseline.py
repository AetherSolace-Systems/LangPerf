"""baseline — trajectories + spans

Revision ID: 0001
Revises:
Create Date: 2026-04-17 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trajectories",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("trace_id", sa.String(), nullable=True),
        sa.Column("service_name", sa.String(), nullable=False),
        sa.Column("environment", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status_tag", sa.String(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("step_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_trajectories_trace_id", "trajectories", ["trace_id"])
    op.create_index("ix_trajectories_service_name", "trajectories", ["service_name"])
    op.create_index("ix_trajectories_environment", "trajectories", ["environment"])
    op.create_index("ix_trajectories_started_at", "trajectories", ["started_at"])
    op.create_index("ix_trajectories_status_tag", "trajectories", ["status_tag"])

    op.create_table(
        "spans",
        sa.Column("span_id", sa.String(), primary_key=True),
        sa.Column("trace_id", sa.String(), nullable=False),
        sa.Column(
            "trajectory_id",
            UUID(as_uuid=False),
            sa.ForeignKey("trajectories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("parent_span_id", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("attributes", JSONB(), nullable=False),
        sa.Column("events", JSONB(), nullable=True),
        sa.Column("status_code", sa.String(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_spans_trace_id", "spans", ["trace_id"])
    op.create_index("ix_spans_trajectory_id", "spans", ["trajectory_id"])
    op.create_index("ix_spans_started_at", "spans", ["started_at"])


def downgrade() -> None:
    op.drop_table("spans")
    op.drop_table("trajectories")

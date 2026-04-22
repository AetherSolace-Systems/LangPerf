"""feedback counters + trajectory completed flag

Revision ID: 0017_feedback_and_completion
Revises: 0016_projects
Create Date: 2026-04-22 00:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision = "0017_feedback_and_completion"
down_revision = "0016_projects"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "trajectories",
        sa.Column(
            "feedback_thumbs_down",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "trajectories",
        sa.Column(
            "feedback_thumbs_up",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "trajectories",
        sa.Column("completed", sa.Boolean, nullable=True),
    )
    op.create_index(
        "ix_trajectories_feedback_thumbs_down",
        "trajectories",
        ["feedback_thumbs_down"],
        postgresql_where=sa.text("feedback_thumbs_down > 0"),
    )


def downgrade() -> None:
    op.drop_index("ix_trajectories_feedback_thumbs_down", table_name="trajectories")
    op.drop_column("trajectories", "completed")
    op.drop_column("trajectories", "feedback_thumbs_up")
    op.drop_column("trajectories", "feedback_thumbs_down")

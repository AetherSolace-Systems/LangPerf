"""agents + agent_versions + trajectory FK columns

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-17 00:01:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agents",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("signature", sa.String(), nullable=False, unique=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("display_name", sa.String(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner", sa.String(), nullable=True),
        sa.Column("github_url", sa.String(), nullable=True),
        sa.Column("language", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_agents_signature", "agents", ["signature"])
    op.create_index("ix_agents_name", "agents", ["name"])

    op.create_table(
        "agent_versions",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "agent_id",
            UUID(as_uuid=False),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("git_sha", sa.String(), nullable=True),
        sa.Column("short_sha", sa.String(), nullable=True),
        sa.Column("package_version", sa.String(), nullable=True),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "agent_id", "git_sha", "package_version", name="uq_agent_version_identity"
        ),
    )
    op.create_index("ix_agent_versions_agent_id", "agent_versions", ["agent_id"])

    op.add_column(
        "trajectories",
        sa.Column(
            "agent_id",
            UUID(as_uuid=False),
            sa.ForeignKey("agents.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "trajectories",
        sa.Column(
            "agent_version_id",
            UUID(as_uuid=False),
            sa.ForeignKey("agent_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_trajectories_agent_id", "trajectories", ["agent_id"])
    op.create_index("ix_trajectories_agent_version_id", "trajectories", ["agent_version_id"])


def downgrade() -> None:
    op.drop_index("ix_trajectories_agent_version_id", table_name="trajectories")
    op.drop_index("ix_trajectories_agent_id", table_name="trajectories")
    op.drop_column("trajectories", "agent_version_id")
    op.drop_column("trajectories", "agent_id")
    op.drop_index("ix_agent_versions_agent_id", table_name="agent_versions")
    op.drop_table("agent_versions")
    op.drop_index("ix_agents_name", table_name="agents")
    op.drop_index("ix_agents_signature", table_name="agents")
    op.drop_table("agents")

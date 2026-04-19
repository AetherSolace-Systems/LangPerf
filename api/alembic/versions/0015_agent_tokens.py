"""agent tokens

Revision ID: 0015_agent_tokens
Revises: 0014_updated_tagged_defaults
Create Date: 2026-04-19 00:00:00.000000
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision = "0015_agent_tokens"
down_revision = "0014_updated_tagged_defaults"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("token_hash", sa.String(255), nullable=True))
    op.add_column("agents", sa.Column("token_prefix", sa.String(24), nullable=True))
    op.add_column("agents", sa.Column("last_token_used_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "agents",
        sa.Column(
            "created_by_user_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_agents_token_prefix", "agents", ["token_prefix"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_agents_token_prefix", table_name="agents")
    op.drop_column("agents", "created_by_user_id")
    op.drop_column("agents", "last_token_used_at")
    op.drop_column("agents", "token_prefix")
    op.drop_column("agents", "token_hash")

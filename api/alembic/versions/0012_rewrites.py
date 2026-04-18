"""rewrites table

Revision ID: 0012_rewrites
Revises: 0011_triage_heuristics
Create Date: 2026-04-17 00:00:00.000000
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID

revision = "0012_rewrites"
down_revision = "0011_triage_heuristics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rewrites",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", PgUUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("trajectory_id", PgUUID(as_uuid=True), sa.ForeignKey("trajectories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_span_id", sa.String(255), nullable=False),
        sa.Column("author_id", PgUUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rationale", sa.Text, nullable=False, server_default=""),
        sa.Column("proposed_steps", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_rewrites_org_id", "rewrites", ["org_id"])
    op.create_index("ix_rewrites_trajectory_id", "rewrites", ["trajectory_id"])
    op.create_index("ix_rewrites_branch_span_id", "rewrites", ["branch_span_id"])


def downgrade() -> None:
    op.drop_index("ix_rewrites_branch_span_id", table_name="rewrites")
    op.drop_index("ix_rewrites_trajectory_id", table_name="rewrites")
    op.drop_index("ix_rewrites_org_id", table_name="rewrites")
    op.drop_table("rewrites")

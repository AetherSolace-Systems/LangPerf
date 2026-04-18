"""triage heuristics: heuristic_hits table

Revision ID: 0011_triage_heuristics
Revises: 0010_collab_primitives
Create Date: 2026-04-17 00:00:00.000000
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID

revision = "0011_triage_heuristics"
down_revision = "0010_collab_primitives"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "heuristic_hits",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", PgUUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("trajectory_id", PgUUID(as_uuid=True), sa.ForeignKey("trajectories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("heuristic", sa.String(64), nullable=False),
        sa.Column("severity", sa.Float, nullable=False),
        sa.Column("signature", sa.String(255), nullable=False),
        sa.Column("details", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_heuristic_hits_org_id", "heuristic_hits", ["org_id"])
    op.create_index("ix_heuristic_hits_trajectory_id", "heuristic_hits", ["trajectory_id"])
    op.create_index("ix_heuristic_hits_heuristic", "heuristic_hits", ["heuristic"])
    op.create_index("ix_heuristic_hits_signature", "heuristic_hits", ["signature"])


def downgrade() -> None:
    op.drop_index("ix_heuristic_hits_signature", table_name="heuristic_hits")
    op.drop_index("ix_heuristic_hits_heuristic", table_name="heuristic_hits")
    op.drop_index("ix_heuristic_hits_trajectory_id", table_name="heuristic_hits")
    op.drop_index("ix_heuristic_hits_org_id", table_name="heuristic_hits")
    op.drop_table("heuristic_hits")

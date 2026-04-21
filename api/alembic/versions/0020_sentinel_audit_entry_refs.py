"""sentinel audit_entry_id cross-ref columns

Revision ID: 0020_sentinel_audit_entry_refs
Revises: 0019_sentinel_ingest_nodes
Create Date: 2026-04-21 12:03:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision = "0020_sentinel_audit_entry_refs"
down_revision = "0019_sentinel_ingest_nodes"
branch_labels = None
depends_on = None

_TABLES_WITH_AUDIT_REF = ["trajectories", "spans", "heuristic_hits"]


def upgrade() -> None:
    for table in _TABLES_WITH_AUDIT_REF:
        op.add_column(
            table,
            sa.Column(
                "audit_entry_id",
                sa.BigInteger,
                sa.ForeignKey("audit_entries.id"),
                nullable=True,
            ),
        )
        op.create_index(
            f"ix_{table}_audit_entry_id",
            table,
            ["audit_entry_id"],
        )


def downgrade() -> None:
    for table in _TABLES_WITH_AUDIT_REF:
        op.drop_index(f"ix_{table}_audit_entry_id", table_name=table)
        op.drop_column(table, "audit_entry_id")

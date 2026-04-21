"""sentinel ingest_nodes (shell — service lands in Plan 2)

Revision ID: 0019_sentinel_ingest_nodes
Revises: 0018_sentinel_agent_identities
Create Date: 2026-04-21 12:02:00.000000
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision = "0019_sentinel_ingest_nodes"
down_revision = "0018_sentinel_agent_identities"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ingest_nodes",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True),
        sa.Column("public_key", sa.LargeBinary, nullable=False),
        sa.Column("public_key_alg", sa.String(32), nullable=False),
        sa.Column("key_storage", sa.String(32), nullable=False),
        sa.Column("tpm_ak_quote", sa.LargeBinary, nullable=True),
        sa.Column(
            "operator_human_id",
            PgUUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "registration_audit_entry_id",
            sa.BigInteger,
            sa.ForeignKey("audit_entries.id"),
            nullable=False,
        ),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("ingest_nodes")

"""sentinel agent_identities (shell — service lands in Plan 2)

Revision ID: 0018_sentinel_agent_identities
Revises: 0017_sentinel_audit_tables
Create Date: 2026-04-21 12:01:00.000000
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision = "0018_sentinel_agent_identities"
down_revision = "0017_sentinel_audit_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_identities",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True),
        sa.Column("public_key", sa.LargeBinary, nullable=False, unique=True),
        sa.Column("public_key_alg", sa.String(32), nullable=False),
        sa.Column("config_hash", sa.LargeBinary(32), nullable=False),
        sa.Column("config_ref", sa.Text, nullable=False),
        sa.Column(
            "tenant_id",
            PgUUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "owner_human_id",
            PgUUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "issuance_audit_entry_id",
            sa.BigInteger,
            sa.ForeignKey("audit_entries.id"),
            nullable=False,
        ),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "revocation_audit_entry_id",
            sa.BigInteger,
            sa.ForeignKey("audit_entries.id"),
            nullable=True,
        ),
        sa.Column("revocation_reason", sa.Text, nullable=True),
    )
    op.create_index(
        "ix_agent_identities_config_hash_tenant",
        "agent_identities",
        ["config_hash", "tenant_id"],
    )
    op.create_index(
        "ix_agent_identities_owner_human_id",
        "agent_identities",
        ["owner_human_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_agent_identities_owner_human_id", table_name="agent_identities")
    op.drop_index("ix_agent_identities_config_hash_tenant", table_name="agent_identities")
    op.drop_table("agent_identities")

"""sentinel audit tables

Revision ID: 0017_sentinel_audit_tables
Revises: 0016_projects
Create Date: 2026-04-21 12:00:00.000000
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision = "0017_sentinel_audit_tables"
down_revision = "0016_projects"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_entries",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("seq", sa.BigInteger, nullable=False, unique=True),
        sa.Column("prev_hash", sa.LargeBinary(32), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("event_payload", sa.LargeBinary, nullable=False),
        sa.Column("event_hash", sa.LargeBinary(32), nullable=False),
        sa.Column("entry_hash", sa.LargeBinary(32), nullable=False),
        sa.Column("agent_id", PgUUID(as_uuid=True), nullable=True),
        sa.Column("principal_human_id", PgUUID(as_uuid=True), nullable=True),
        sa.Column("agent_signature", sa.LargeBinary, nullable=True),
        sa.Column("ingest_node_id", PgUUID(as_uuid=True), nullable=False),
        sa.Column("ingest_signature", sa.LargeBinary, nullable=False),
        sa.Column(
            "ts",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("agent_ts", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_audit_entries_event_type_ts", "audit_entries", ["event_type", "ts"])
    op.create_index("ix_audit_entries_agent_id_ts", "audit_entries", ["agent_id", "ts"])
    op.create_index(
        "ix_audit_entries_principal_human_id_ts",
        "audit_entries",
        ["principal_human_id", "ts"],
    )

    if op.get_context().dialect.name == "postgresql":
        op.execute(
            """
            CREATE OR REPLACE FUNCTION audit_entries_append_only() RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'audit_entries is append-only';
            END;
            $$ LANGUAGE plpgsql;

            CREATE TRIGGER audit_entries_no_update
                BEFORE UPDATE ON audit_entries
                FOR EACH ROW EXECUTE FUNCTION audit_entries_append_only();

            CREATE TRIGGER audit_entries_no_delete
                BEFORE DELETE ON audit_entries
                FOR EACH ROW EXECUTE FUNCTION audit_entries_append_only();
            """
        )

    op.create_table(
        "audit_roots",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("tree_size", sa.BigInteger, nullable=False, unique=True),
        sa.Column("root_hash", sa.LargeBinary(32), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingest_node_id", PgUUID(as_uuid=True), nullable=False),
        sa.Column("ingest_signature", sa.LargeBinary, nullable=False),
    )

    op.create_table(
        "external_anchors",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "root_id",
            sa.BigInteger,
            sa.ForeignKey("audit_roots.id"),
            nullable=False,
        ),
        sa.Column("anchor_type", sa.String(32), nullable=False),
        sa.Column("anchor_payload", sa.LargeBinary, nullable=False),
        sa.Column("anchored_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("anchor_ref", sa.Text, nullable=True),
    )
    op.create_index("ix_external_anchors_root_id", "external_anchors", ["root_id"])


def downgrade() -> None:
    if op.get_context().dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS audit_entries_no_delete ON audit_entries;")
        op.execute("DROP TRIGGER IF EXISTS audit_entries_no_update ON audit_entries;")
        op.execute("DROP FUNCTION IF EXISTS audit_entries_append_only();")
    op.drop_index("ix_external_anchors_root_id", table_name="external_anchors")
    op.drop_table("external_anchors")
    op.drop_table("audit_roots")
    op.drop_index("ix_audit_entries_principal_human_id_ts", table_name="audit_entries")
    op.drop_index("ix_audit_entries_agent_id_ts", table_name="audit_entries")
    op.drop_index("ix_audit_entries_event_type_ts", table_name="audit_entries")
    op.drop_table("audit_entries")

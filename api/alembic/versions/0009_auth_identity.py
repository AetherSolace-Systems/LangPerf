"""auth identity + tenancy

Revision ID: 0009_auth_identity
Revises: 0008
Create Date: 2026-04-17 00:00:00.000000
"""
import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID

revision = "0009_auth_identity"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "users",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column(
            "is_admin", sa.Boolean, nullable=False, server_default=sa.text("false")
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("org_id", "email", name="uq_users_org_email"),
    )
    op.create_table(
        "sessions",
        sa.Column("token", sa.String(64), primary_key=True),
        sa.Column(
            "user_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )

    default_org_id = uuid.uuid4()
    op.execute(
        sa.text(
            "INSERT INTO organizations (id, name, slug, created_at)"
            " VALUES (:id, 'default', 'default', :ts)"
        ).bindparams(
            sa.bindparam("id", value=default_org_id, type_=PgUUID(as_uuid=True)),
            sa.bindparam("ts", value=datetime.now(timezone.utc)),
        )
    )

    for table in ("agents", "trajectories"):
        op.add_column(table, sa.Column("org_id", PgUUID(as_uuid=True), nullable=True))
        op.execute(
            sa.text(f"UPDATE {table} SET org_id = :id").bindparams(
                sa.bindparam("id", value=default_org_id, type_=PgUUID(as_uuid=True))
            )
        )
        op.alter_column(table, "org_id", nullable=False)
        op.create_foreign_key(
            f"fk_{table}_org_id",
            table,
            "organizations",
            ["org_id"],
            ["id"],
            ondelete="CASCADE",
        )
        op.create_index(f"ix_{table}_org_id", table, ["org_id"])

    op.add_column(
        "workspace_settings", sa.Column("org_id", PgUUID(as_uuid=True), nullable=True)
    )
    op.execute(
        sa.text("UPDATE workspace_settings SET org_id = :id").bindparams(
            sa.bindparam("id", value=default_org_id, type_=PgUUID(as_uuid=True))
        )
    )
    op.drop_constraint("workspace_settings_pkey", "workspace_settings", type_="primary")
    op.alter_column("workspace_settings", "org_id", nullable=False)
    op.create_primary_key(
        "pk_workspace_settings", "workspace_settings", ["org_id", "key"]
    )
    op.create_foreign_key(
        "fk_workspace_settings_org_id",
        "workspace_settings",
        "organizations",
        ["org_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_workspace_settings_org_id", "workspace_settings", type_="foreignkey"
    )
    op.drop_constraint("pk_workspace_settings", "workspace_settings", type_="primary")
    op.create_primary_key("workspace_settings_pkey", "workspace_settings", ["key"])
    op.drop_column("workspace_settings", "org_id")

    for table in ("trajectories", "agents"):
        op.drop_index(f"ix_{table}_org_id", table_name=table)
        op.drop_constraint(f"fk_{table}_org_id", table, type_="foreignkey")
        op.drop_column(table, "org_id")

    op.drop_table("sessions")
    op.drop_table("users")
    op.drop_table("organizations")

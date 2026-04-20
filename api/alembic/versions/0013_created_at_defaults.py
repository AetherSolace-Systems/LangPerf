"""add server_default now() to created_at on v2 tables

Revision ID: 0013_created_at_defaults
Revises: 0012_rewrites
Create Date: 2026-04-18 00:00:00.000000

Fixes a gap in 0009 and 0010: seven tables were created with
`created_at NOT NULL` but no DB-level default. The ORM models declared
`server_default=func.now()` but that only affects DDL through
Base.metadata.create_all — not migrations. Any ORM insert that omitted
created_at hit NotNullViolationError.
"""
import sqlalchemy as sa
from alembic import op

revision = "0013_created_at_defaults"
down_revision = "0012_rewrites"
branch_labels = None
depends_on = None


# Tables whose ORM mapping has server_default=func.now() on `created_at`
# but whose migration-created column landed without a DB default.
_TABLES = [
    "organizations",
    "users",
    "sessions",
    "comments",
    "notifications",
    "shared_links",
    "failure_modes",
]


def upgrade() -> None:
    for table in _TABLES:
        op.alter_column(
            table,
            "created_at",
            server_default=sa.text("now()"),
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=False,
        )


def downgrade() -> None:
    for table in _TABLES:
        op.alter_column(
            table,
            "created_at",
            server_default=None,
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=False,
        )

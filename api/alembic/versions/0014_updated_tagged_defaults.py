"""add server_default now() for updated_at / tagged_at on v2 tables

Revision ID: 0014_updated_tagged_defaults
Revises: 0013_created_at_defaults
Create Date: 2026-04-18 00:00:01.000000

Catch-up sibling of 0013. Same root cause — ORM models declared
server_default=func.now() but the migration-created columns landed
without a DB default, so ORM inserts that omitted the column hit
NotNullViolationError.
"""
import sqlalchemy as sa
from alembic import op

revision = "0014_updated_tagged_defaults"
down_revision = "0013_created_at_defaults"
branch_labels = None
depends_on = None


_COLUMNS = [
    ("comments", "updated_at"),
    ("trajectory_failure_modes", "tagged_at"),
]


def upgrade() -> None:
    for table, column in _COLUMNS:
        op.alter_column(
            table,
            column,
            server_default=sa.text("now()"),
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=False,
        )


def downgrade() -> None:
    for table, column in _COLUMNS:
        op.alter_column(
            table,
            column,
            server_default=None,
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=False,
        )

"""collab primitives: comments, notifications, shared_links, failure_modes, trajectory_failure_modes

Revision ID: 0010_collab_primitives
Revises: 0009_auth_identity
Create Date: 2026-04-17 00:00:00.000000
"""
import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID

revision = "0010_collab_primitives"
down_revision = "0009_auth_identity"
branch_labels = None
depends_on = None

# Default failure modes to seed for every org:
# (slug, label, color)
DEFAULT_FAILURE_MODES = [
    ("wrong_tool", "Wrong tool", "warn"),
    ("bad_args", "Bad args", "warn"),
    ("hallucination", "Hallucination", "peach-neon"),
    ("loop", "Loop", "peach-neon"),
    ("misunderstood_intent", "Misunderstood intent", "steel-mist"),
]


def upgrade() -> None:
    # 1. Create comments table
    op.create_table(
        "comments",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "trajectory_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("trajectories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("span_id", sa.String(255), nullable=True),
        sa.Column(
            "author_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "parent_comment_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("comments.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("resolved", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 2. Create indexes on comments
    op.create_index("ix_comments_trajectory_id", "comments", ["trajectory_id"])
    op.create_index("ix_comments_span_id", "comments", ["span_id"])

    # 3. Create comment_mentions table
    op.create_table(
        "comment_mentions",
        sa.Column(
            "comment_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("comments.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    # 4. Create notifications table
    op.create_table(
        "notifications",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("payload", JSONB, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])

    # 5. Create shared_links table
    op.create_table(
        "shared_links",
        sa.Column("token", sa.String(64), primary_key=True),
        sa.Column(
            "org_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "trajectory_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("trajectories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_by",
            PgUUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 6. Create failure_modes table
    op.create_table(
        "failure_modes",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("slug", sa.String(64), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("color", sa.String(32), nullable=False, server_default=sa.text("'steel-mist'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("org_id", "slug", name="uq_failure_modes_org_slug"),
    )

    # 7. Create trajectory_failure_modes table
    op.create_table(
        "trajectory_failure_modes",
        sa.Column(
            "trajectory_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("trajectories.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "failure_mode_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("failure_modes.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "tagged_by",
            PgUUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tagged_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 8. Add assigned_user_id to trajectories
    op.add_column(
        "trajectories",
        sa.Column(
            "assigned_user_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_trajectories_assigned_user_id", "trajectories", ["assigned_user_id"]
    )

    # 9. Seed default failure modes for every existing org
    now = datetime.now(timezone.utc)
    conn = op.get_bind()
    orgs = conn.execute(sa.text("SELECT id FROM organizations")).fetchall()
    for (org_id,) in orgs:
        for slug, label, color in DEFAULT_FAILURE_MODES:
            fm_id = uuid.uuid4()
            op.execute(
                sa.text(
                    "INSERT INTO failure_modes (id, org_id, slug, label, color, created_at)"
                    " VALUES (:id, :org_id, :slug, :label, :color, :created_at)"
                ).bindparams(
                    sa.bindparam("id", value=fm_id, type_=PgUUID(as_uuid=True)),
                    sa.bindparam("org_id", value=org_id, type_=PgUUID(as_uuid=True)),
                    sa.bindparam("slug", value=slug),
                    sa.bindparam("label", value=label),
                    sa.bindparam("color", value=color),
                    sa.bindparam("created_at", value=now),
                )
            )


def downgrade() -> None:
    # Reverse in opposite order

    # Remove assigned_user_id from trajectories
    op.drop_index("ix_trajectories_assigned_user_id", table_name="trajectories")
    op.drop_column("trajectories", "assigned_user_id")

    # Drop tables in dependency order
    op.drop_table("trajectory_failure_modes")
    op.drop_table("failure_modes")
    op.drop_table("shared_links")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_table("notifications")
    op.drop_table("comment_mentions")
    op.drop_index("ix_comments_span_id", table_name="comments")
    op.drop_index("ix_comments_trajectory_id", table_name="comments")
    op.drop_table("comments")

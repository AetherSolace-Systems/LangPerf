"""projects

Revision ID: 0016_projects
Revises: 0015_agent_tokens
Create Date: 2026-04-19 00:00:00.000000
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PgUUID
import uuid

revision = "0016_projects"
down_revision = "0015_agent_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("color", sa.String(32), nullable=True),
        sa.Column(
            "created_by_user_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("org_id", "slug", name="uq_projects_org_slug"),
    )
    op.create_index("ix_projects_org_id", "projects", ["org_id"])

    conn = op.get_bind()
    orgs = conn.execute(sa.text("SELECT id FROM organizations")).fetchall()
    for (org_id,) in orgs:
        proj_id = uuid.uuid4()
        op.execute(
            sa.text(
                "INSERT INTO projects (id, org_id, name, slug) "
                "VALUES (:id, :org_id, 'Default', 'default')"
            ).bindparams(
                sa.bindparam("id", value=proj_id, type_=PgUUID(as_uuid=True)),
                sa.bindparam("org_id", value=org_id, type_=PgUUID(as_uuid=True)),
            )
        )

    op.add_column(
        "agents",
        sa.Column("project_id", PgUUID(as_uuid=True), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE agents SET project_id = ("
            "  SELECT p.id FROM projects p WHERE p.org_id = agents.org_id AND p.slug = 'default'"
            ")"
        )
    )
    op.alter_column("agents", "project_id", nullable=False)
    op.create_foreign_key(
        "fk_agents_project_id",
        "agents",
        "projects",
        ["project_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_agents_project_id", "agents", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_agents_project_id", table_name="agents")
    op.drop_constraint("fk_agents_project_id", "agents", type_="foreignkey")
    op.drop_column("agents", "project_id")
    op.drop_index("ix_projects_org_id", table_name="projects")
    op.drop_table("projects")

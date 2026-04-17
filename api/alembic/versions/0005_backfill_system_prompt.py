"""backfill trajectories.system_prompt from existing LLM spans

Populates system_prompt for any trajectory that has at least one LLM span
whose `llm.input_messages.0.message.role` == "system". Idempotent — only
touches rows where system_prompt IS NULL.

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-17 00:04:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE trajectories SET system_prompt = sub.content
            FROM (
                SELECT DISTINCT ON (s.trajectory_id)
                    s.trajectory_id,
                    s.attributes->>'llm.input_messages.0.message.content' AS content
                FROM spans s
                WHERE s.kind = 'llm'
                  AND s.attributes->>'llm.input_messages.0.message.role' = 'system'
                  AND (s.attributes ? 'llm.input_messages.0.message.content')
                ORDER BY s.trajectory_id, s.started_at
            ) sub
            WHERE trajectories.id = sub.trajectory_id
              AND trajectories.system_prompt IS NULL
            """
        )
    )


def downgrade() -> None:
    pass

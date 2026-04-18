"""backfill trajectories.input_tokens + output_tokens from existing spans

Sums `llm.token_count.prompt` / `gen_ai.usage.input_tokens` and
`llm.token_count.completion` / `gen_ai.usage.output_tokens` across each
trajectory's LLM spans. Idempotent — only touches rows whose current
input_tokens + output_tokens == 0 (the default-seeded state).

Revision ID: 0007
Revises: 0006
Create Date: 2026-04-17 00:06:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            WITH sums AS (
                SELECT
                    trajectory_id,
                    SUM(
                        COALESCE(
                            NULLIF(attributes->>'llm.token_count.prompt', '')::int,
                            NULLIF(attributes->>'gen_ai.usage.input_tokens', '')::int,
                            0
                        )
                    ) AS in_tok,
                    SUM(
                        COALESCE(
                            NULLIF(attributes->>'llm.token_count.completion', '')::int,
                            NULLIF(attributes->>'gen_ai.usage.output_tokens', '')::int,
                            0
                        )
                    ) AS out_tok
                FROM spans
                WHERE kind = 'llm'
                GROUP BY trajectory_id
            )
            UPDATE trajectories
               SET input_tokens = sums.in_tok,
                   output_tokens = sums.out_tok
              FROM sums
             WHERE trajectories.id = sums.trajectory_id
               AND trajectories.input_tokens = 0
               AND trajectories.output_tokens = 0
            """
        )
    )


def downgrade() -> None:
    pass

"""Schema-level tests for migration 0010_collab_primitives.

These tests validate that the SQLAlchemy models declare the expected tables and
columns (via Base.metadata.create_all in the conftest `engine` fixture). They
do NOT execute the Alembic migration itself — live migration validation is done
separately against a throwaway Postgres instance.
"""

from sqlalchemy import inspect


async def test_migration_creates_collab_tables(engine):
    async with engine.connect() as conn:
        def inspect_tables(sync_conn):
            insp = inspect(sync_conn)
            return set(insp.get_table_names())
        tables = await conn.run_sync(inspect_tables)
    for name in ("comments", "comment_mentions", "notifications", "shared_links", "failure_modes", "trajectory_failure_modes"):
        assert name in tables


async def test_trajectory_has_assigned_user_id(engine):
    async with engine.connect() as conn:
        def inspect_cols(sync_conn):
            insp = inspect(sync_conn)
            return {c["name"] for c in insp.get_columns("trajectories")}
        cols = await conn.run_sync(inspect_cols)
    assert "assigned_user_id" in cols

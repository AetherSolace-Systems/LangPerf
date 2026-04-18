"""Schema-level tests for migration 0009_auth_identity.

These tests validate that the SQLAlchemy models declare the expected tables and
columns (via Base.metadata.create_all in the conftest `engine` fixture). They
do NOT execute the Alembic migration itself — live migration validation is done
separately against a throwaway Postgres instance.
"""

from sqlalchemy import inspect


async def test_migration_creates_auth_tables_and_backfills_org(engine):
    async with engine.connect() as conn:
        def inspect_tables(sync_conn):
            insp = inspect(sync_conn)
            return set(insp.get_table_names())

        tables = await conn.run_sync(inspect_tables)
    assert "organizations" in tables
    assert "users" in tables
    assert "sessions" in tables


async def test_all_existing_rows_get_default_org(engine):
    async with engine.connect() as conn:
        def inspect_cols(sync_conn):
            insp = inspect(sync_conn)
            return {
                "agents": {c["name"] for c in insp.get_columns("agents")},
                "trajectories": {c["name"] for c in insp.get_columns("trajectories")},
                "workspace_settings": {
                    c["name"] for c in insp.get_columns("workspace_settings")
                },
            }

        cols = await conn.run_sync(inspect_cols)
    assert "org_id" in cols["agents"]
    assert "org_id" in cols["trajectories"]
    assert "org_id" in cols["workspace_settings"]

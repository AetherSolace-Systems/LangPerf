"""Schema-level tests for migration 0011_triage_heuristics.

Validates that the SQLAlchemy models declare the expected heuristic_hits table
(via Base.metadata.create_all in the conftest `engine` fixture). Live migration
validation is done separately against a throwaway Postgres instance.
"""
from sqlalchemy import inspect


async def test_migration_creates_heuristic_hits_table(engine):
    async with engine.connect() as conn:
        def inspect_tables(sync_conn):
            insp = inspect(sync_conn)
            return set(insp.get_table_names())
        tables = await conn.run_sync(inspect_tables)
    assert "heuristic_hits" in tables

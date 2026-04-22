"""agent_failures.render_csv — header + filtering + URL column."""
from __future__ import annotations

import csv
import io

import pytest

from app.services.agent_failures import render_csv


@pytest.mark.asyncio
async def test_csv_has_expected_header(session, seed_agent):
    agent = await seed_agent()
    body = b""
    async for chunk in render_csv(
        session, agent_id=agent.id, window="7d", web_base_url="https://lp.example"
    ):
        body += chunk
    reader = csv.reader(io.StringIO(body.decode()))
    header = next(reader)
    assert header == [
        "trajectory_id",
        "started_at",
        "heuristics",
        "tools_errored",
        "latency_ms",
        "cost_usd",
        "status_tag",
        "feedback_thumbs_down",
        "notes",
        "url",
    ]


@pytest.mark.asyncio
async def test_csv_empty_agent_returns_header_only(session, seed_agent):
    agent = await seed_agent()
    body = b""
    async for chunk in render_csv(
        session, agent_id=agent.id, window="7d", web_base_url="https://lp.example"
    ):
        body += chunk
    lines = [ln for ln in body.decode().splitlines() if ln]
    assert len(lines) == 1


@pytest.mark.asyncio
async def test_csv_includes_heuristic_flagged_rows(
    session, seed_agent_with_heuristic_hits
):
    agent = await seed_agent_with_heuristic_hits(
        hits=[{"heuristic": "tool_error", "tool": "search_orders", "count": 4}]
    )
    body = b""
    async for chunk in render_csv(
        session, agent_id=agent.id, window="7d", web_base_url="https://lp.example"
    ):
        body += chunk
    lines = [ln for ln in body.decode().splitlines() if ln]
    assert len(lines) >= 5  # header + 4 flagged rows


@pytest.mark.asyncio
async def test_csv_url_column_is_valid(
    session, seed_agent_with_heuristic_hits
):
    agent = await seed_agent_with_heuristic_hits(
        hits=[{"heuristic": "tool_error", "tool": "foo", "count": 1}]
    )
    body = b""
    async for chunk in render_csv(
        session, agent_id=agent.id, window="7d", web_base_url="https://lp.example"
    ):
        body += chunk
    reader = csv.reader(io.StringIO(body.decode()))
    header = next(reader)
    url_idx = header.index("url")
    row = next(reader)
    assert row[url_idx].startswith("https://lp.example/t/")

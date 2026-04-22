"""Render a deterministic markdown profile of an agent for download.

Sections: header, snapshot (4 KPIs), top issues, tool landscape, recent patterns.
f-string template (no Jinja). Golden-file testable.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import Integer, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Agent,
    FailureMode,
    HeuristicHit,
    Span,
    Trajectory,
    TrajectoryFailureMode,
)
from app.services import agent_worklist


WINDOW_LABEL = {"24h": "24 hours", "7d": "7 days", "30d": "30 days"}


async def render_markdown(
    session: AsyncSession,
    *,
    agent_id: str,
    window: str = "7d",
) -> str:
    agent = (
        await session.execute(select(Agent).where(Agent.id == agent_id))
    ).scalar_one()

    hours = agent_worklist.WINDOW_HOURS[window]
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(hours=hours)

    snapshot = await _snapshot(session, agent_id, window_start, now, hours)
    issues = await agent_worklist.compute(session, agent_id=agent_id, window=window)
    tools = await _tool_landscape(session, agent_id, window_start)
    patterns = await _pattern_counts(session, agent_id, window_start)

    parts: list[str] = []
    parts.append(f"# {agent.name}")
    parts.append(f"Window: last {WINDOW_LABEL[window]} ending {now.date().isoformat()}")
    parts.append("")

    parts.append("## Snapshot")
    if snapshot["runs"] == 0:
        parts.append("_No data in window._")
    else:
        parts.append(f"- runs: {snapshot['runs']}")
        parts.append(
            f"- p95 latency: {_fmt_ms(snapshot['p95'])}{_delta_str(snapshot['p95_delta'])}"
        )
        parts.append(f"- tool success: {_fmt_pct(snapshot['tool_ok_rate'])}")
        parts.append(f"- user \U0001f44e: {snapshot['feedback_down']}")
    parts.append("")

    parts.append("## Top issues")
    if not issues:
        parts.append("_Nothing ranked high enough to surface._")
    else:
        for i, it in enumerate(issues[:5], start=1):
            parts.append(
                f"{i}. **{it['title']}** — {it['urgency']} urgency, {it['affected_runs']} affected"
            )
    parts.append("")

    parts.append("## Tool landscape")
    if not tools:
        parts.append("_No tool calls in window._")
    else:
        parts.append("| tool | calls | ok % | p95 ms |")
        parts.append("| --- | --- | --- | --- |")
        for t in tools[:10]:
            parts.append(
                f"| `{t['name']}` | {t['calls']} | {_fmt_pct(t['ok_rate'])} | {_fmt_ms(t['p95'])} |"
            )
    parts.append("")

    parts.append("## Recent patterns")
    if not patterns:
        parts.append("_No failure-mode tags in window._")
    else:
        for p in patterns:
            parts.append(f"- {p['label']}: {p['count']}")

    return "\n".join(parts) + "\n"


async def _snapshot(session, agent_id, window_start, now, hours):
    prior_start = now - timedelta(hours=2 * hours)
    dialect = session.bind.dialect.name if session.bind else "unknown"

    runs = int(
        (
            await session.execute(
                select(func.count()).where(
                    Trajectory.agent_id == agent_id,
                    Trajectory.started_at >= window_start,
                )
            )
        ).scalar()
        or 0
    )

    # percentile_cont is postgres-only
    p95 = None
    p95_prior = None
    if dialect == "postgresql":
        p95 = (
            await session.execute(
                select(func.percentile_cont(0.95).within_group(Trajectory.duration_ms)).where(
                    Trajectory.agent_id == agent_id,
                    Trajectory.started_at >= window_start,
                    Trajectory.duration_ms.isnot(None),
                )
            )
        ).scalar()
        p95_prior = (
            await session.execute(
                select(func.percentile_cont(0.95).within_group(Trajectory.duration_ms)).where(
                    Trajectory.agent_id == agent_id,
                    Trajectory.started_at >= prior_start,
                    Trajectory.started_at < window_start,
                    Trajectory.duration_ms.isnot(None),
                )
            )
        ).scalar()
    p95_delta = None
    if p95 is not None and p95_prior is not None and p95_prior > 0:
        p95_delta = (p95 / p95_prior) - 1.0

    # JSON astext subscript is postgres-only; return None for tool stats on sqlite.
    tool_ok_rate = None
    if dialect == "postgresql":
        tool_row = (
            await session.execute(
                select(
                    func.sum(case((Span.status_code == "ERROR", 0), else_=1).cast(Integer)),
                    func.count(),
                )
                .join(Trajectory, Trajectory.id == Span.trajectory_id)
                .where(
                    Trajectory.agent_id == agent_id,
                    Span.started_at >= window_start,
                    Span.attributes["langperf.node.kind"].astext.in_(["tool", "tool_call"]),
                )
            )
        ).one()
        ok, total = tool_row
        tool_ok_rate = (ok or 0) / total if total else None

    fb_down = int(
        (
            await session.execute(
                select(func.coalesce(func.sum(Trajectory.feedback_thumbs_down), 0)).where(
                    Trajectory.agent_id == agent_id,
                    Trajectory.started_at >= window_start,
                )
            )
        ).scalar()
        or 0
    )

    return {
        "runs": runs,
        "p95": float(p95) if p95 is not None else None,
        "p95_delta": p95_delta,
        "tool_ok_rate": tool_ok_rate,
        "feedback_down": fb_down,
    }


async def _tool_landscape(session, agent_id, window_start):
    # JSON astext subscript (JSONB) is postgres-only; sqlite returns empty.
    dialect = session.bind.dialect.name if session.bind else "unknown"
    if dialect != "postgresql":
        return []

    ok_expr = func.sum(
        case((Span.status_code == "ERROR", 0), else_=1).cast(Integer)
    ).label("ok")

    stmt = (
        select(
            Span.attributes["tool.name"].astext.label("tool"),
            func.count().label("calls"),
            ok_expr,
            func.percentile_cont(0.95).within_group(Span.duration_ms).label("p95"),
        )
        .join(Trajectory, Trajectory.id == Span.trajectory_id)
        .where(
            Trajectory.agent_id == agent_id,
            Span.started_at >= window_start,
            Span.attributes["langperf.node.kind"].astext.in_(["tool", "tool_call"]),
        )
        .group_by("tool")
        .order_by(func.count().desc())
    )
    rows = (await session.execute(stmt)).all()
    out = []
    for r in rows:
        if not r.tool:
            continue
        p95 = getattr(r, "p95", None)
        out.append(
            {
                "name": r.tool,
                "calls": int(r.calls),
                "ok_rate": float(r.ok or 0) / float(r.calls),
                "p95": float(p95) if p95 is not None else None,
            }
        )
    return out


async def _pattern_counts(session, agent_id, window_start):
    stmt = (
        select(FailureMode.label, func.count().label("n"))
        .join(TrajectoryFailureMode, TrajectoryFailureMode.failure_mode_id == FailureMode.id)
        .join(Trajectory, Trajectory.id == TrajectoryFailureMode.trajectory_id)
        .where(
            Trajectory.agent_id == agent_id,
            TrajectoryFailureMode.tagged_at >= window_start,
        )
        .group_by(FailureMode.label)
        .order_by(func.count().desc())
    )
    rows = (await session.execute(stmt)).all()
    return [{"label": r.label, "count": int(r.n)} for r in rows]


def _fmt_ms(v):
    if v is None:
        return "\u2014"
    if v >= 1000:
        return f"{v / 1000:.2f}s"
    return f"{int(v)}ms"


def _fmt_pct(v):
    if v is None:
        return "\u2014"
    return f"{v * 100:.1f}%"


def _delta_str(delta):
    if delta is None:
        return ""
    pct = delta * 100
    arrow = "\u2191" if pct > 0 else "\u2193"
    return f" ({arrow}{abs(pct):.0f}% vs. prior)"

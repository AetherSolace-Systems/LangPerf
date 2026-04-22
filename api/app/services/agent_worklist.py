"""Agent worklist — ranked issues for the agent's detail page.

Score formula (one pure function, exposed for direct unit tests):
    score = SEVERITY[signal] × log2(affected_runs + 1) × recency_decay(hours_since_last_seen)
    recency_decay(h) = 2 ** (-h / 168)   # 1-week half-life
    urgency: ≥8 high, ≥4 med, else low
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import Integer, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import HeuristicHit, Span, Trajectory


SEVERITY = {
    # heuristic-driven (key = heuristic slug)
    "tool_error":     3,
    "loop":           3,
    "latency_outlier": 2,
    "low_confidence": 2,
    "apology_phrase": 1,
    # feedback-driven
    "thumbs_down":    3,
    # delta-driven (aggregate)
    "cost_delta":     2,
    "latency_delta":  2,
    "completion_drop": 3,
    "tool_success_drop": 2,
}


WINDOW_HOURS = {"24h": 24, "7d": 168, "30d": 720}


@dataclass
class WorklistItem:
    signal: str
    title: str
    subtitle: str
    affected_runs: int
    last_seen_at: datetime
    severity: int
    score: float
    urgency: str

    def as_dict(self) -> dict:
        d = asdict(self)
        d["last_seen_at"] = self.last_seen_at.isoformat()
        return d


def score(severity: int, affected_runs: int, last_seen_at: datetime) -> float:
    now = datetime.now(timezone.utc)
    # Guard against tz-naive inputs (shouldn't happen but defend).
    if last_seen_at.tzinfo is None:
        last_seen_at = last_seen_at.replace(tzinfo=timezone.utc)
    hours_since = max(0.0, (now - last_seen_at).total_seconds() / 3600.0)
    decay = 2.0 ** (-hours_since / 168.0)
    return severity * math.log2(affected_runs + 1) * decay


def urgency_bucket(s: float) -> str:
    if s >= 8:
        return "high"
    if s >= 4:
        return "med"
    return "low"


async def compute(
    session: AsyncSession,
    *,
    agent_id: str,
    window: str = "7d",
) -> list[dict]:
    hours = WINDOW_HOURS[window]
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(hours=hours)
    prior_start = now - timedelta(hours=2 * hours)

    items: list[WorklistItem] = []
    items.extend(await _heuristic_candidates(session, agent_id, window_start))
    items.extend(await _feedback_candidates(session, agent_id, window_start, now))
    items.extend(
        await _delta_candidates(session, agent_id, window_start, prior_start, now)
    )

    items.sort(key=lambda it: (-it.score, -it.last_seen_at.timestamp()))
    return [it.as_dict() for it in items[:20]]


async def _heuristic_candidates(
    session: AsyncSession,
    agent_id: str,
    window_start: datetime,
) -> list[WorklistItem]:
    """Group HeuristicHits by (heuristic, tool-from-details-JSON).
    On sqlite we emulate via a Python-side fetch-then-group because JSON
    `->>` ordering in GROUP BY is brittle across dialects; on modest
    dogfood data volumes this is fast enough."""
    stmt = (
        select(
            HeuristicHit.heuristic,
            HeuristicHit.details,
            HeuristicHit.created_at,
        )
        .join(Trajectory, Trajectory.id == HeuristicHit.trajectory_id)
        .where(
            Trajectory.agent_id == agent_id,
            HeuristicHit.created_at >= window_start,
        )
    )
    rows = (await session.execute(stmt)).all()
    # Group by (heuristic, tool_name_or_none)
    groups: dict[tuple[str, str | None], dict] = {}
    for r in rows:
        tool = None
        if isinstance(r.details, dict):
            tool = r.details.get("tool")
        key = (r.heuristic, tool)
        g = groups.setdefault(
            key,
            {"count": 0, "last_seen": r.created_at},
        )
        g["count"] += 1
        if r.created_at > g["last_seen"]:
            g["last_seen"] = r.created_at

    out: list[WorklistItem] = []
    for (heuristic, tool), g in groups.items():
        sev = SEVERITY.get(heuristic, 1)
        s = score(sev, g["count"], g["last_seen"])
        title = (
            f"{heuristic.replace('_', ' ')} in `{tool}`"
            if tool
            else heuristic.replace("_", " ")
        )
        out.append(
            WorklistItem(
                signal=f"heuristic:{heuristic}",
                title=title,
                subtitle=f"{g['count']} runs affected",
                affected_runs=g["count"],
                last_seen_at=g["last_seen"],
                severity=sev,
                score=s,
                urgency=urgency_bucket(s),
            )
        )
    return out


async def _feedback_candidates(
    session: AsyncSession,
    agent_id: str,
    window_start: datetime,
    now: datetime,
) -> list[WorklistItem]:
    row = (
        await session.execute(
            select(
                func.count().label("n_trajs"),
                func.coalesce(func.sum(Trajectory.feedback_thumbs_down), 0).label("n_down"),
                func.max(Trajectory.started_at).label("last_seen"),
            ).where(
                Trajectory.agent_id == agent_id,
                Trajectory.started_at >= window_start,
                Trajectory.feedback_thumbs_down > 0,
            )
        )
    ).one()
    if not row.n_trajs:
        return []
    sev = SEVERITY["thumbs_down"]
    affected = int(row.n_down or 0)
    last_seen = row.last_seen or now
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)
    s = score(sev, affected, last_seen)
    return [
        WorklistItem(
            signal="feedback:thumbs_down",
            title=f"{affected} thumbs-down events",
            subtitle=f"{row.n_trajs} trajectories flagged",
            affected_runs=affected,
            last_seen_at=last_seen,
            severity=sev,
            score=s,
            urgency=urgency_bucket(s),
        )
    ]


async def _delta_candidates(
    session: AsyncSession,
    agent_id: str,
    window_start: datetime,
    prior_start: datetime,
    now: datetime,
) -> list[WorklistItem]:
    """Window-vs-prior-window deltas on p95 latency, completion rate,
    and per-tool success rate. On sqlite (no percentile_cont) this
    returns empty for latency but still emits completion/per-tool."""
    out: list[WorklistItem] = []

    dialect = session.bind.dialect.name if session.bind else "unknown"

    # p95 latency delta (postgres only)
    if dialect == "postgresql":
        window_p95 = await _p95_latency(session, agent_id, window_start, now)
        prior_p95 = await _p95_latency(session, agent_id, prior_start, window_start)
        if window_p95 and prior_p95 and window_p95 / prior_p95 >= 1.25:
            sev = SEVERITY["latency_delta"]
            affected = await _trajectory_count(session, agent_id, window_start, now)
            s = score(sev, max(1, affected), now)
            out.append(
                WorklistItem(
                    signal="delta:latency",
                    title=f"p95 latency climbed {((window_p95 / prior_p95) - 1) * 100:.0f}%",
                    subtitle=f"{prior_p95:.0f}ms → {window_p95:.0f}ms",
                    affected_runs=affected,
                    last_seen_at=now,
                    severity=sev,
                    score=s,
                    urgency=urgency_bucket(s),
                )
            )

    # Completion-rate drop (requires ≥10 trajectories in each window)
    window_cr = await _completion_rate(session, agent_id, window_start, now)
    prior_cr = await _completion_rate(session, agent_id, prior_start, window_start)
    if window_cr is not None and prior_cr is not None and (prior_cr - window_cr) >= 0.05:
        sev = SEVERITY["completion_drop"]
        affected = await _trajectory_count(session, agent_id, window_start, now)
        s = score(sev, max(1, affected), now)
        out.append(
            WorklistItem(
                signal="delta:completion_drop",
                title=f"completion rate dropped {(prior_cr - window_cr) * 100:.1f}pp",
                subtitle=f"{prior_cr * 100:.0f}% → {window_cr * 100:.0f}%",
                affected_runs=affected,
                last_seen_at=now,
                severity=sev,
                score=s,
                urgency=urgency_bucket(s),
            )
        )

    # Per-tool success drop
    out.extend(await _tool_success_drops(session, agent_id, window_start, prior_start, now))
    return out


async def _p95_latency(
    session: AsyncSession,
    agent_id: str,
    start: datetime,
    end: datetime,
) -> float | None:
    """Postgres only. Callers must guard dialect."""
    row = (
        await session.execute(
            select(
                func.percentile_cont(0.95).within_group(Trajectory.duration_ms)
            ).where(
                Trajectory.agent_id == agent_id,
                Trajectory.started_at >= start,
                Trajectory.started_at < end,
                Trajectory.duration_ms.isnot(None),
            )
        )
    ).scalar()
    return float(row) if row is not None else None


async def _trajectory_count(
    session: AsyncSession,
    agent_id: str,
    start: datetime,
    end: datetime,
) -> int:
    return int(
        (
            await session.execute(
                select(func.count()).where(
                    Trajectory.agent_id == agent_id,
                    Trajectory.started_at >= start,
                    Trajectory.started_at < end,
                )
            )
        ).scalar()
        or 0
    )


async def _completion_rate(
    session: AsyncSession,
    agent_id: str,
    start: datetime,
    end: datetime,
) -> float | None:
    row = (
        await session.execute(
            select(
                func.sum(case((Trajectory.completed.is_(True), 1), else_=0).cast(Integer)),
                func.sum(case((Trajectory.completed.is_(None), 0), else_=1).cast(Integer)),
            ).where(
                Trajectory.agent_id == agent_id,
                Trajectory.started_at >= start,
                Trajectory.started_at < end,
            )
        )
    ).one()
    completed, total = row
    if not total or total < 10:
        return None
    return float(completed or 0) / float(total)


async def _tool_success_drops(
    session: AsyncSession,
    agent_id: str,
    window_start: datetime,
    prior_start: datetime,
    now: datetime,
) -> list[WorklistItem]:
    # JSON astext subscript is postgres-only; sqlite returns empty here.
    dialect = session.bind.dialect.name if session.bind else "unknown"
    if dialect != "postgresql":
        return []
    window_stats = await _tool_stats(session, agent_id, window_start, now)
    prior_stats = await _tool_stats(session, agent_id, prior_start, window_start)
    out: list[WorklistItem] = []
    for tool, (w_ok, w_total) in window_stats.items():
        if w_total < 10:
            continue
        p_ok, p_total = prior_stats.get(tool, (0, 0))
        if p_total == 0:
            continue
        w_rate = w_ok / w_total
        p_rate = p_ok / p_total
        drop = p_rate - w_rate
        if drop >= 0.05:
            sev = SEVERITY["tool_success_drop"]
            s = score(sev, w_total, now)
            out.append(
                WorklistItem(
                    signal=f"delta:tool_success:{tool}",
                    title=f"`{tool}` success dropped {drop * 100:.1f}pp",
                    subtitle=f"{p_rate * 100:.0f}% → {w_rate * 100:.0f}% ({w_total} calls)",
                    affected_runs=w_total,
                    last_seen_at=now,
                    severity=sev,
                    score=s,
                    urgency=urgency_bucket(s),
                )
            )
    return out


async def _tool_stats(
    session: AsyncSession,
    agent_id: str,
    start: datetime,
    end: datetime,
) -> dict[str, tuple[int, int]]:
    ok_expr = func.sum(
        case((Span.status_code == "ERROR", 0), else_=1).cast(Integer)
    ).label("ok")
    stmt = (
        select(
            Span.attributes["tool.name"].astext.label("tool"),
            ok_expr,
            func.count().label("total"),
        )
        .join(Trajectory, Trajectory.id == Span.trajectory_id)
        .where(
            Trajectory.agent_id == agent_id,
            Span.started_at >= start,
            Span.started_at < end,
            Span.attributes["langperf.node.kind"].astext.in_(["tool", "tool_call"]),
        )
        .group_by("tool")
    )
    rows = (await session.execute(stmt)).all()
    return {r.tool: (int(r.ok or 0), int(r.total or 0)) for r in rows if r.tool}

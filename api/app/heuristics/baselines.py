import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Span, Trajectory


async def compute_p95_baselines(db: AsyncSession, org_id: str) -> dict[tuple[str | None, str], float]:
    q = (
        select(Trajectory.agent_id, Span.attributes, Span.duration_ms)
        .join(Span, Span.trajectory_id == Trajectory.id)
        .where(Trajectory.org_id == org_id, Span.kind == "tool")
    )
    rows = (await db.execute(q)).all()
    buckets: dict[tuple[str | None, str], list[int]] = {}
    for agent_id, attrs, duration_ms in rows:
        if duration_ms is None:
            continue
        tool = (attrs or {}).get("tool.name") or "unknown"
        key = (agent_id, tool)
        buckets.setdefault(key, []).append(duration_ms)
    return {
        k: _percentile(sorted(v), 0.95)
        for k, v in buckets.items()
        if len(v) >= 5
    }


def _percentile(sorted_values: list[int], p: float) -> float:
    if not sorted_values:
        return 0.0
    k = (len(sorted_values) - 1) * p
    f = int(k)
    c = min(f + 1, len(sorted_values) - 1)
    if f == c:
        return float(sorted_values[f])
    return sorted_values[f] + (sorted_values[c] - sorted_values[f]) * (k - f)

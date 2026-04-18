from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.heuristics.apology_phrase import ApologyPhraseHeuristic
from app.heuristics.baselines import compute_p95_baselines
from app.heuristics.latency_outlier import LatencyOutlierHeuristic
from app.heuristics.loop import LoopHeuristic
from app.heuristics.low_confidence import LowConfidenceHeuristic
from app.heuristics.tool_error import ToolErrorHeuristic
from app.heuristics.types import Heuristic, HeuristicContext
from app.models import HeuristicHit, Span, Trajectory

HEURISTICS: list[Heuristic] = [
    ToolErrorHeuristic(),
    LatencyOutlierHeuristic(),
    ApologyPhraseHeuristic(),
    LoopHeuristic(),
    LowConfidenceHeuristic(),
]


async def evaluate_trajectory(db: AsyncSession, trajectory_id: str) -> int:
    trajectory = await db.get(Trajectory, trajectory_id)
    if trajectory is None:
        return 0
    spans = (
        (await db.execute(
            select(Span).where(Span.trajectory_id == trajectory_id).order_by(Span.started_at.asc())
        ))
        .scalars()
        .all()
    )
    span_dicts = [
        {
            "span_id": s.span_id, "trace_id": s.trace_id, "parent_span_id": s.parent_span_id,
            "name": s.name, "kind": s.kind, "status_code": s.status_code,
            "started_at": s.started_at, "ended_at": s.ended_at, "duration_ms": s.duration_ms,
            "attributes": s.attributes or {}, "events": s.events or [],
        }
        for s in spans
    ]

    baselines_raw = await compute_p95_baselines(db, trajectory.org_id)
    baselines = {k[1]: v for k, v in baselines_raw.items() if k[0] == trajectory.agent_id or k[0] is None}

    ctx = HeuristicContext(
        trajectory_id=str(trajectory.id),
        org_id=str(trajectory.org_id),
        spans=span_dicts,
        baselines=baselines,
    )

    await db.execute(delete(HeuristicHit).where(HeuristicHit.trajectory_id == trajectory_id))

    total = 0
    for h in HEURISTICS:
        for hit in h.evaluate(ctx):
            db.add(
                HeuristicHit(
                    org_id=trajectory.org_id,
                    trajectory_id=trajectory.id,
                    heuristic=hit.heuristic,
                    severity=hit.severity,
                    signature=hit.signature,
                    details=hit.details,
                )
            )
            total += 1
    await db.commit()
    return total

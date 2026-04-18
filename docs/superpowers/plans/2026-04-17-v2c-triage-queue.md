# V2c — Triage Queue + Heuristics + Clustering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a queue-first triage surface that surfaces the highest-priority trajectories to review. Five automated heuristics score every trajectory; a heuristic-based clustering algorithm groups similar failures; the queue replaces the dashboard as the default landing page for logged-in users.

**Architecture:** A pluggable heuristic evaluation pipeline runs on every trajectory after ingestion (via a post-ingest hook on `/v1/traces`) and on existing trajectories via a backfill command. Each heuristic is a small, pure function over a trajectory's spans that returns zero or more `HeuristicHit` rows. Hits are stored in a dedicated `heuristic_hits` table with `(trajectory_id, heuristic, details)`. A `HeuristicSignature` derived from the set of hits per trajectory drives clustering — two trajectories in the same cluster share the same signature (heuristic slug set plus a canonical normalization of their hit details). Clusters are computed lazily on the queue endpoint.

**Tech Stack:** Continuation of v2a/v2b stack. New dependency: none (pure Python heuristics). Heuristics are pure functions ⇒ heavily unit-tested.

**Depends on:** v2a (auth + org scoping) and v2b (failure-mode taxonomy model — signature generation uses failure mode tags as auxiliary signals).

---

## File Structure

**Backend:**
- `api/app/models.py` — add `HeuristicHit` model
- `api/alembic/versions/0011_triage_heuristics.py` — migration
- `api/app/heuristics/__init__.py` — `Heuristic` protocol + registry
- `api/app/heuristics/types.py` — `HeuristicHit`, `HeuristicContext` dataclasses
- `api/app/heuristics/tool_error.py`
- `api/app/heuristics/latency_outlier.py`
- `api/app/heuristics/apology_phrase.py`
- `api/app/heuristics/loop.py`
- `api/app/heuristics/low_confidence.py`
- `api/app/heuristics/engine.py` — evaluates all heuristics for a trajectory, persists hits
- `api/app/heuristics/baselines.py` — computes per-agent+tool p95 latency baselines
- `api/app/services/cluster.py` — signature computation + cluster grouping
- `api/app/api/triage.py` — queue endpoints
- `api/app/api/clusters.py` — cluster endpoints
- `api/app/ingest/hook.py` — post-ingest heuristic dispatch hook (called from `/v1/traces` handler)
- `api/app/cli/backfill_heuristics.py` — CLI to backfill heuristics for existing trajectories
- `api/app/main.py` — register new routers, wire post-ingest hook
- Tests per heuristic + engine + cluster + API

**Frontend:**
- `web/lib/triage.ts` — client helpers
- `web/app/queue/page.tsx` — default landing page after login
- `web/components/queue/queue-row.tsx`
- `web/components/queue/cluster-card.tsx`
- `web/components/queue/filter-bar.tsx`
- `web/components/queue/heuristic-badge.tsx`
- Update `web/middleware.ts` default redirect to `/queue` instead of `/`
- `web/tests/triage.spec.ts` — Playwright

---

## Task 1: HeuristicHit model + migration

**Files:**
- Modify: `api/app/models.py`
- Create: `api/alembic/versions/0011_triage_heuristics.py`
- Create: `api/tests/test_models_heuristic_hit.py`

- [ ] **Step 1: Failing test**

```python
from app.models import HeuristicHit, Organization, Trajectory


async def test_heuristic_hit_can_be_created(session):
    org = Organization(name="default", slug="default")
    session.add(org); await session.flush()
    t = Trajectory(org_id=org.id, trace_id="t", service_name="svc", name="n")
    session.add(t); await session.flush()
    hit = HeuristicHit(
        org_id=org.id,
        trajectory_id=t.id,
        heuristic="tool_error",
        severity=0.8,
        signature="tool_error:search_orders",
        details={"tool": "search_orders", "message": "timeout"},
    )
    session.add(hit)
    await session.commit()
    assert hit.id is not None
```

- [ ] **Step 2: Fail.**

- [ ] **Step 3: Add model**

```python
class HeuristicHit(Base):
    __tablename__ = "heuristic_hits"

    id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    trajectory_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("trajectories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    heuristic: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    severity: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    signature: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
```

- [ ] **Step 4: Migration**

```python
# api/alembic/versions/0011_triage_heuristics.py
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID

revision = "0011_triage_heuristics"
down_revision = "0010_collab_primitives"


def upgrade() -> None:
    op.create_table(
        "heuristic_hits",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", PgUUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("trajectory_id", PgUUID(as_uuid=True), sa.ForeignKey("trajectories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("heuristic", sa.String(64), nullable=False),
        sa.Column("severity", sa.Float, nullable=False),
        sa.Column("signature", sa.String(255), nullable=False),
        sa.Column("details", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_heuristic_hits_trajectory_id", "heuristic_hits", ["trajectory_id"])
    op.create_index("ix_heuristic_hits_heuristic", "heuristic_hits", ["heuristic"])
    op.create_index("ix_heuristic_hits_signature", "heuristic_hits", ["signature"])


def downgrade() -> None:
    op.drop_index("ix_heuristic_hits_signature", table_name="heuristic_hits")
    op.drop_index("ix_heuristic_hits_heuristic", table_name="heuristic_hits")
    op.drop_index("ix_heuristic_hits_trajectory_id", table_name="heuristic_hits")
    op.drop_table("heuristic_hits")
```

- [ ] **Step 5: Pass + commit**

```bash
cd api && pytest tests/test_models_heuristic_hit.py -v
git add api/app/models.py api/alembic/versions/0011_triage_heuristics.py api/tests/test_models_heuristic_hit.py
git commit -m "feat: heuristic_hits model + migration"
```

---

## Task 2: Heuristic protocol + types

**Files:**
- Create: `api/app/heuristics/__init__.py`
- Create: `api/app/heuristics/types.py`
- Create: `api/tests/test_heuristic_types.py`

- [ ] **Step 1: Failing test**

```python
from app.heuristics.types import HeuristicContext, HeuristicHit


def test_heuristic_hit_is_constructable():
    hit = HeuristicHit(heuristic="tool_error", severity=0.9, signature="tool_error:foo", details={})
    assert hit.heuristic == "tool_error"


def test_heuristic_context_exposes_spans():
    ctx = HeuristicContext(
        trajectory_id="t", org_id="o", spans=[{"span_id": "s1", "name": "x"}], baselines={}
    )
    assert ctx.spans[0]["span_id"] == "s1"
```

- [ ] **Step 2: Fail.**

- [ ] **Step 3: Implement types + protocol**

```python
# api/app/heuristics/types.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class HeuristicHit:
    heuristic: str
    severity: float
    signature: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class HeuristicContext:
    trajectory_id: str
    org_id: str
    spans: list[dict[str, Any]]
    baselines: dict[str, Any]


class Heuristic(Protocol):
    slug: str

    def evaluate(self, ctx: HeuristicContext) -> list[HeuristicHit]: ...
```

```python
# api/app/heuristics/__init__.py
from app.heuristics.types import Heuristic, HeuristicContext, HeuristicHit

__all__ = ["Heuristic", "HeuristicContext", "HeuristicHit"]
```

- [ ] **Step 4: Pass + commit**

```bash
git add api/app/heuristics api/tests/test_heuristic_types.py
git commit -m "feat: heuristic protocol + types"
```

---

## Task 3: Tool-error heuristic

**Files:**
- Create: `api/app/heuristics/tool_error.py`
- Create: `api/tests/heuristics/test_tool_error.py`

- [ ] **Step 1: Failing test**

```python
from app.heuristics.tool_error import ToolErrorHeuristic
from app.heuristics.types import HeuristicContext


def _ctx(spans):
    return HeuristicContext(trajectory_id="t", org_id="o", spans=spans, baselines={})


def test_flags_tool_span_with_error_status():
    spans = [
        {"span_id": "s1", "kind": "tool", "name": "search_orders", "status_code": "ERROR", "attributes": {"tool.name": "search_orders"}, "events": [{"name": "exception", "attributes": {"exception.message": "timeout"}}]},
    ]
    hits = ToolErrorHeuristic().evaluate(_ctx(spans))
    assert len(hits) == 1
    assert hits[0].heuristic == "tool_error"
    assert "search_orders" in hits[0].signature


def test_no_hit_on_ok_tool_spans():
    spans = [{"span_id": "s1", "kind": "tool", "name": "ok_tool", "status_code": "OK", "attributes": {}, "events": []}]
    assert ToolErrorHeuristic().evaluate(_ctx(spans)) == []
```

- [ ] **Step 2: Fail.**

- [ ] **Step 3: Implement**

```python
# api/app/heuristics/tool_error.py
from app.heuristics.types import HeuristicContext, HeuristicHit


class ToolErrorHeuristic:
    slug = "tool_error"

    def evaluate(self, ctx: HeuristicContext) -> list[HeuristicHit]:
        hits: list[HeuristicHit] = []
        for span in ctx.spans:
            if span.get("kind") != "tool":
                continue
            if (span.get("status_code") or "").upper() != "ERROR":
                continue
            tool_name = (span.get("attributes") or {}).get("tool.name") or span.get("name") or "unknown"
            message = ""
            for ev in span.get("events") or []:
                if (ev.get("name") or "") == "exception":
                    message = (ev.get("attributes") or {}).get("exception.message") or ""
                    break
            hits.append(
                HeuristicHit(
                    heuristic=self.slug,
                    severity=0.8,
                    signature=f"{self.slug}:{tool_name}",
                    details={"tool": tool_name, "message": message, "span_id": span.get("span_id")},
                )
            )
        return hits
```

- [ ] **Step 4: Pass + commit**

```bash
git add api/app/heuristics/tool_error.py api/tests/heuristics
git commit -m "feat: tool_error heuristic"
```

---

## Task 4: Latency outlier heuristic + baselines

**Files:**
- Create: `api/app/heuristics/baselines.py`
- Create: `api/app/heuristics/latency_outlier.py`
- Create: `api/tests/heuristics/test_latency_outlier.py`
- Create: `api/tests/heuristics/test_baselines.py`

- [ ] **Step 1: Baseline test**

```python
from app.heuristics.baselines import compute_p95_baselines


async def test_p95_baselines(session):
    from app.models import Agent, Organization, Span, Trajectory
    org = Organization(name="default", slug="default"); session.add(org); await session.flush()
    agent = Agent(org_id=org.id, signature="sig", name="agent-a", display_name="A")
    session.add(agent); await session.flush()
    t = Trajectory(org_id=org.id, trace_id="t", service_name="svc", name="n", agent_id=agent.id)
    session.add(t); await session.flush()
    for i, dur in enumerate([10, 15, 20, 25, 30, 35, 40, 50, 100, 500]):
        session.add(Span(
            span_id=f"s{i}", trace_id="t", trajectory_id=t.id, name="search", kind="tool",
            duration_ms=dur, attributes={"tool.name": "search"},
        ))
    await session.commit()
    baselines = await compute_p95_baselines(session, org.id)
    assert baselines[(agent.id, "search")] > 35
```

- [ ] **Step 2: Outlier test**

```python
from app.heuristics.latency_outlier import LatencyOutlierHeuristic
from app.heuristics.types import HeuristicContext


def test_flags_span_exceeding_p95_by_margin():
    ctx = HeuristicContext(
        trajectory_id="t", org_id="o",
        spans=[{"span_id": "s1", "kind": "tool", "name": "search", "duration_ms": 5000, "attributes": {"tool.name": "search"}}],
        baselines={"search": 100.0},  # keyed by tool name for simplicity
    )
    hits = LatencyOutlierHeuristic().evaluate(ctx)
    assert len(hits) == 1
    assert hits[0].heuristic == "latency_outlier"


def test_no_flag_within_p95_margin():
    ctx = HeuristicContext(
        trajectory_id="t", org_id="o",
        spans=[{"span_id": "s1", "kind": "tool", "name": "search", "duration_ms": 120, "attributes": {"tool.name": "search"}}],
        baselines={"search": 100.0},
    )
    assert LatencyOutlierHeuristic().evaluate(ctx) == []
```

- [ ] **Step 3: Implement baselines**

```python
# api/app/heuristics/baselines.py
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Span, Trajectory


async def compute_p95_baselines(db: AsyncSession, org_id: uuid.UUID) -> dict[tuple[uuid.UUID | None, str], float]:
    q = (
        select(Trajectory.agent_id, Span.attributes, Span.duration_ms)
        .join(Span, Span.trajectory_id == Trajectory.id)
        .where(Trajectory.org_id == org_id, Span.kind == "tool")
    )
    rows = (await db.execute(q)).all()
    buckets: dict[tuple[uuid.UUID | None, str], list[int]] = {}
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
```

- [ ] **Step 4: Implement heuristic**

```python
# api/app/heuristics/latency_outlier.py
from app.heuristics.types import HeuristicContext, HeuristicHit

MARGIN = 2.0  # flagged if > 2× the p95 baseline


class LatencyOutlierHeuristic:
    slug = "latency_outlier"

    def evaluate(self, ctx: HeuristicContext) -> list[HeuristicHit]:
        hits: list[HeuristicHit] = []
        for span in ctx.spans:
            if span.get("kind") != "tool":
                continue
            duration = span.get("duration_ms")
            if duration is None:
                continue
            tool = (span.get("attributes") or {}).get("tool.name") or span.get("name") or "unknown"
            baseline = ctx.baselines.get(tool)
            if not baseline or duration < baseline * MARGIN:
                continue
            hits.append(
                HeuristicHit(
                    heuristic=self.slug,
                    severity=min(1.0, duration / max(baseline, 1) / 5.0),
                    signature=f"{self.slug}:{tool}",
                    details={"tool": tool, "duration_ms": duration, "baseline_p95": baseline},
                )
            )
        return hits
```

- [ ] **Step 5: Pass + commit**

```bash
cd api && pytest tests/heuristics/test_baselines.py tests/heuristics/test_latency_outlier.py -v
git add api/app/heuristics/baselines.py api/app/heuristics/latency_outlier.py api/tests/heuristics
git commit -m "feat: latency_outlier heuristic + p95 baselines"
```

---

## Task 5: Apology-phrase heuristic

**Files:**
- Create: `api/app/heuristics/apology_phrase.py`
- Create: `api/tests/heuristics/test_apology_phrase.py`

- [ ] **Step 1: Failing test**

```python
from app.heuristics.apology_phrase import ApologyPhraseHeuristic
from app.heuristics.types import HeuristicContext


def _ctx(final_output: str):
    return HeuristicContext(
        trajectory_id="t", org_id="o",
        spans=[
            {"span_id": "s1", "kind": "llm", "attributes": {"gen_ai.response.finish_reason": "stop"}},
            {"span_id": "s2", "kind": "llm", "name": "final", "attributes": {"gen_ai.response.text": final_output}},
        ],
        baselines={},
    )


def test_flags_apology_phrase():
    hits = ApologyPhraseHeuristic().evaluate(_ctx("I'm sorry, I can't help with that."))
    assert len(hits) == 1


def test_no_flag_when_no_apology():
    hits = ApologyPhraseHeuristic().evaluate(_ctx("Here are the results."))
    assert hits == []
```

- [ ] **Step 2: Fail.**

- [ ] **Step 3: Implement**

```python
# api/app/heuristics/apology_phrase.py
import re

from app.heuristics.types import HeuristicContext, HeuristicHit

PHRASES = [
    r"i'?m sorry",
    r"i apologi[sz]e",
    r"i can'?t (help|assist|do)",
    r"as an ai language model",
    r"i do not have",
    r"unable to (help|assist|provide)",
]
PATTERN = re.compile("|".join(PHRASES), re.IGNORECASE)


class ApologyPhraseHeuristic:
    slug = "apology_phrase"

    def evaluate(self, ctx: HeuristicContext) -> list[HeuristicHit]:
        final_outputs = []
        for span in ctx.spans:
            if span.get("kind") != "llm":
                continue
            text = (span.get("attributes") or {}).get("gen_ai.response.text")
            if not text:
                continue
            final_outputs.append((span.get("span_id"), text))
        if not final_outputs:
            return []
        # Only the last LLM output counts as the "final"
        span_id, text = final_outputs[-1]
        match = PATTERN.search(text)
        if not match:
            return []
        phrase = match.group(0).lower()
        return [
            HeuristicHit(
                heuristic=self.slug,
                severity=0.6,
                signature=f"{self.slug}:{phrase}",
                details={"phrase": phrase, "span_id": span_id, "excerpt": text[max(0, match.start() - 30):match.end() + 30]},
            )
        ]
```

- [ ] **Step 4: Pass + commit**

```bash
git add api/app/heuristics/apology_phrase.py api/tests/heuristics/test_apology_phrase.py
git commit -m "feat: apology_phrase heuristic"
```

---

## Task 6: Loop detection heuristic

**Files:**
- Create: `api/app/heuristics/loop.py`
- Create: `api/tests/heuristics/test_loop.py`

- [ ] **Step 1: Failing test**

```python
from app.heuristics.loop import LoopHeuristic
from app.heuristics.types import HeuristicContext

REPEAT_THRESHOLD = 3


def test_detects_loop_of_repeated_tool_calls():
    spans = [
        {"span_id": f"s{i}", "kind": "tool", "name": "search", "attributes": {"tool.name": "search", "tool.arguments": {"q": "foo"}}}
        for i in range(4)
    ]
    hits = LoopHeuristic().evaluate(HeuristicContext(trajectory_id="t", org_id="o", spans=spans, baselines={}))
    assert len(hits) == 1
    assert hits[0].details["count"] == 4


def test_no_loop_below_threshold():
    spans = [
        {"span_id": "s1", "kind": "tool", "name": "search", "attributes": {"tool.name": "search", "tool.arguments": {"q": "foo"}}},
    ]
    assert LoopHeuristic().evaluate(HeuristicContext(trajectory_id="t", org_id="o", spans=spans, baselines={})) == []
```

- [ ] **Step 2: Fail.**

- [ ] **Step 3: Implement**

```python
# api/app/heuristics/loop.py
import json

from app.heuristics.types import HeuristicContext, HeuristicHit

THRESHOLD = 3


def _fingerprint(span: dict) -> str:
    kind = span.get("kind") or ""
    name = (span.get("attributes") or {}).get("tool.name") or span.get("name") or ""
    args = (span.get("attributes") or {}).get("tool.arguments") or {}
    try:
        canonical = json.dumps(args, sort_keys=True, default=str)
    except Exception:
        canonical = str(args)
    return f"{kind}:{name}:{canonical}"


class LoopHeuristic:
    slug = "loop"

    def evaluate(self, ctx: HeuristicContext) -> list[HeuristicHit]:
        counts: dict[str, list[str]] = {}
        for span in ctx.spans:
            if span.get("kind") != "tool":
                continue
            fp = _fingerprint(span)
            counts.setdefault(fp, []).append(span.get("span_id"))
        hits: list[HeuristicHit] = []
        for fp, span_ids in counts.items():
            if len(span_ids) >= THRESHOLD:
                tool = fp.split(":", 2)[1]
                hits.append(
                    HeuristicHit(
                        heuristic=self.slug,
                        severity=min(1.0, len(span_ids) / 10.0),
                        signature=f"{self.slug}:{tool}",
                        details={"tool": tool, "count": len(span_ids), "span_ids": span_ids},
                    )
                )
        return hits
```

- [ ] **Step 4: Pass + commit**

```bash
git add api/app/heuristics/loop.py api/tests/heuristics/test_loop.py
git commit -m "feat: loop detection heuristic"
```

---

## Task 7: Low-confidence / refusal heuristic

**Files:**
- Create: `api/app/heuristics/low_confidence.py`
- Create: `api/tests/heuristics/test_low_confidence.py`

Signals checked:
- `gen_ai.response.finish_reason == "content_filter"` or `"refusal"`
- `logprobs` summary (if present) indicating low confidence
- Short final-output length (<10 chars) — likely a hedge/refusal

- [ ] **Step 1: Failing tests**

```python
from app.heuristics.low_confidence import LowConfidenceHeuristic
from app.heuristics.types import HeuristicContext


def test_flags_refusal_finish_reason():
    spans = [{"span_id": "s", "kind": "llm", "attributes": {"gen_ai.response.finish_reason": "content_filter", "gen_ai.response.text": "..."}}]
    hits = LowConfidenceHeuristic().evaluate(HeuristicContext(trajectory_id="t", org_id="o", spans=spans, baselines={}))
    assert len(hits) == 1


def test_flags_very_short_output():
    spans = [{"span_id": "s", "kind": "llm", "attributes": {"gen_ai.response.finish_reason": "stop", "gen_ai.response.text": "ok"}}]
    hits = LowConfidenceHeuristic().evaluate(HeuristicContext(trajectory_id="t", org_id="o", spans=spans, baselines={}))
    assert len(hits) == 1
```

- [ ] **Step 2: Fail.**

- [ ] **Step 3: Implement**

```python
# api/app/heuristics/low_confidence.py
from app.heuristics.types import HeuristicContext, HeuristicHit

MIN_FINAL_OUTPUT_LEN = 10
REFUSAL_REASONS = {"content_filter", "refusal"}


class LowConfidenceHeuristic:
    slug = "low_confidence"

    def evaluate(self, ctx: HeuristicContext) -> list[HeuristicHit]:
        llm_spans = [s for s in ctx.spans if s.get("kind") == "llm"]
        if not llm_spans:
            return []
        final = llm_spans[-1]
        attrs = final.get("attributes") or {}
        reason = attrs.get("gen_ai.response.finish_reason")
        text = attrs.get("gen_ai.response.text") or ""
        hits: list[HeuristicHit] = []
        if reason in REFUSAL_REASONS:
            hits.append(
                HeuristicHit(
                    heuristic=self.slug,
                    severity=0.7,
                    signature=f"{self.slug}:{reason}",
                    details={"reason": reason, "span_id": final.get("span_id")},
                )
            )
        elif len(text.strip()) < MIN_FINAL_OUTPUT_LEN:
            hits.append(
                HeuristicHit(
                    heuristic=self.slug,
                    severity=0.4,
                    signature=f"{self.slug}:short_output",
                    details={"length": len(text), "span_id": final.get("span_id")},
                )
            )
        return hits
```

- [ ] **Step 4: Pass + commit**

```bash
git add api/app/heuristics/low_confidence.py api/tests/heuristics/test_low_confidence.py
git commit -m "feat: low_confidence heuristic"
```

---

## Task 8: Heuristic engine — run all, persist hits

**Files:**
- Create: `api/app/heuristics/engine.py`
- Create: `api/tests/heuristics/test_engine.py`

- [ ] **Step 1: Failing test**

```python
from app.heuristics.engine import evaluate_trajectory
from app.models import Organization, Span, Trajectory


async def test_engine_persists_hits_for_tool_error(session):
    org = Organization(name="default", slug="default"); session.add(org); await session.flush()
    t = Trajectory(org_id=org.id, trace_id="t", service_name="svc", name="n")
    session.add(t); await session.flush()
    session.add(Span(
        span_id="s1", trace_id="t", trajectory_id=t.id, name="search_orders",
        kind="tool", status_code="ERROR",
        attributes={"tool.name": "search_orders"},
        events=[{"name": "exception", "attributes": {"exception.message": "timeout"}}],
    ))
    await session.commit()

    n_hits = await evaluate_trajectory(session, t.id)
    assert n_hits >= 1
    from sqlalchemy import select
    from app.models import HeuristicHit
    hits = (await session.execute(select(HeuristicHit).where(HeuristicHit.trajectory_id == t.id))).scalars().all()
    assert any(h.heuristic == "tool_error" for h in hits)
```

- [ ] **Step 2: Fail.**

- [ ] **Step 3: Implement engine**

```python
# api/app/heuristics/engine.py
import uuid
from datetime import datetime, timezone

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


async def evaluate_trajectory(db: AsyncSession, trajectory_id: uuid.UUID) -> int:
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
    # Collapse (agent_id, tool) → tool for the flat baselines dict used by heuristics
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
```

- [ ] **Step 4: Pass + commit**

```bash
git add api/app/heuristics/engine.py api/tests/heuristics/test_engine.py
git commit -m "feat: heuristic engine evaluates + persists all 5"
```

---

## Task 9: Post-ingest hook + backfill CLI

**Files:**
- Create: `api/app/ingest/__init__.py` (empty if missing)
- Create: `api/app/ingest/hook.py`
- Create: `api/app/cli/__init__.py`
- Create: `api/app/cli/backfill_heuristics.py`
- Modify: `api/app/main.py` (where `/v1/traces` is handled) — call hook after ingest commit

- [ ] **Step 1: Hook implementation**

```python
# api/app/ingest/hook.py
import asyncio
import logging
import uuid

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.heuristics.engine import evaluate_trajectory

logger = logging.getLogger(__name__)


async def run_heuristics_for_trajectories(
    session_factory: async_sessionmaker, trajectory_ids: list[uuid.UUID]
) -> None:
    for tid in trajectory_ids:
        try:
            async with session_factory() as db:
                await evaluate_trajectory(db, tid)
        except Exception as exc:
            logger.exception("heuristic evaluation failed for %s: %s", tid, exc)


def schedule_heuristics(
    session_factory: async_sessionmaker, trajectory_ids: list[uuid.UUID]
) -> None:
    # Fire-and-forget — do not block the ingest response.
    asyncio.create_task(run_heuristics_for_trajectories(session_factory, trajectory_ids))
```

- [ ] **Step 2: Wire into ingest**

Modify the `/v1/traces` handler in `api/app/main.py` (or wherever it lives) — after committing ingested trajectories, call:

```python
from app.ingest.hook import schedule_heuristics
schedule_heuristics(SessionLocal, list(persisted_trajectory_ids))
```

- [ ] **Step 3: Backfill CLI**

```python
# api/app/cli/backfill_heuristics.py
import asyncio
import sys
import uuid

from sqlalchemy import select

from app.db import SessionLocal
from app.heuristics.engine import evaluate_trajectory
from app.models import Trajectory


async def main(limit: int | None = None) -> None:
    async with SessionLocal() as db:
        q = select(Trajectory.id).order_by(Trajectory.started_at.desc())
        if limit:
            q = q.limit(limit)
        ids = [row[0] for row in (await db.execute(q)).all()]
    total = 0
    for tid in ids:
        async with SessionLocal() as db:
            total += await evaluate_trajectory(db, tid)
    print(f"evaluated {len(ids)} trajectories, wrote {total} hits")


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    asyncio.run(main(limit))
```

Run: `cd api && python -m app.cli.backfill_heuristics 100`

- [ ] **Step 4: Commit**

```bash
git add api/app/ingest api/app/cli api/app/main.py
git commit -m "feat: post-ingest heuristic hook + backfill CLI"
```

---

## Task 10: Cluster signature service

**Files:**
- Create: `api/app/services/cluster.py`
- Create: `api/tests/test_cluster.py`

- [ ] **Step 1: Failing test**

```python
from app.services.cluster import trajectory_signature


def test_signature_from_hits_is_stable_and_sorted():
    hits = [
        {"heuristic": "tool_error", "signature": "tool_error:search_orders"},
        {"heuristic": "loop", "signature": "loop:search_orders"},
    ]
    a = trajectory_signature(hits)
    b = trajectory_signature(list(reversed(hits)))
    assert a == b
    assert "tool_error:search_orders" in a
```

- [ ] **Step 2: Fail.**

- [ ] **Step 3: Implement**

```python
# api/app/services/cluster.py
import hashlib
from collections import defaultdict
from collections.abc import Iterable
from typing import TypedDict


class HitLike(TypedDict, total=False):
    heuristic: str
    signature: str


def trajectory_signature(hits: Iterable[HitLike]) -> str:
    sigs = sorted({h["signature"] for h in hits if h.get("signature")})
    return "|".join(sigs)


def signature_hash(signature: str) -> str:
    return hashlib.sha1(signature.encode("utf-8")).hexdigest()[:12]


def group_trajectories_by_signature(
    rows: Iterable[tuple[str, str]]
) -> dict[str, list[str]]:
    """rows: (trajectory_id, signature)"""
    out: dict[str, list[str]] = defaultdict(list)
    for tid, sig in rows:
        out[sig].append(tid)
    return dict(out)
```

- [ ] **Step 4: Pass + commit**

```bash
git add api/app/services/cluster.py api/tests/test_cluster.py
git commit -m "feat: cluster signature + grouping helpers"
```

---

## Task 11: Triage queue API

**Files:**
- Create: `api/app/api/triage.py`
- Modify: `api/app/main.py`
- Create: `api/tests/test_api_triage.py`

- [ ] **Step 1: Failing test**

```python
async def _bootstrap(client):
    await client.post(
        "/api/auth/signup",
        json={"email": "a@b", "password": "pw12345678", "display_name": "A"},
    )


async def test_queue_returns_scored_trajectories(client, session):
    await _bootstrap(client)
    from app.heuristics.engine import evaluate_trajectory
    from app.models import Organization, Span, Trajectory
    from sqlalchemy import select
    org = (await session.execute(select(Organization))).scalar_one()
    t = Trajectory(org_id=org.id, trace_id="t", service_name="svc", name="n")
    session.add(t); await session.flush()
    session.add(Span(
        span_id="s1", trace_id="t", trajectory_id=t.id, name="search",
        kind="tool", status_code="ERROR",
        attributes={"tool.name": "search"},
        events=[{"name": "exception", "attributes": {"exception.message": "timeout"}}],
    ))
    await session.commit()
    await evaluate_trajectory(session, t.id)

    r = await client.get("/api/queue")
    assert r.status_code == 200
    body = r.json()
    assert body["items"]
    assert body["items"][0]["trajectory_id"] == str(t.id)
    assert body["items"][0]["hits"]
```

- [ ] **Step 2: Fail.**

- [ ] **Step 3: Implement**

```python
# api/app/api/triage.py
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_user
from app.db import get_session
from app.models import HeuristicHit, Trajectory, TrajectoryFailureMode

router = APIRouter(prefix="/api/queue", tags=["triage"])


@router.get("")
async def queue(
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
    heuristic: list[str] = Query(default_factory=list),
    assigned_to_me: bool = False,
    limit: int = 50,
    offset: int = 0,
):
    # Score: sum of hit severities, clamped at 1.0 per heuristic to avoid hot spots dominating.
    severity_sum = func.sum(func.least(HeuristicHit.severity, 1.0)).label("score")

    base = (
        select(Trajectory, severity_sum, func.count(HeuristicHit.id).label("hit_count"))
        .join(HeuristicHit, HeuristicHit.trajectory_id == Trajectory.id)
        .where(Trajectory.org_id == user.org_id)
        .group_by(Trajectory.id)
    )
    if heuristic:
        base = base.where(HeuristicHit.heuristic.in_(heuristic))
    if assigned_to_me:
        base = base.where(Trajectory.assigned_user_id == user.id)

    base = base.order_by(severity_sum.desc(), Trajectory.started_at.desc()).limit(limit).offset(offset)
    results = (await session.execute(base)).all()

    items = []
    for traj, score, hit_count in results:
        hits_q = select(HeuristicHit).where(HeuristicHit.trajectory_id == traj.id)
        hits = (await session.execute(hits_q)).scalars().all()
        items.append({
            "trajectory_id": str(traj.id),
            "name": traj.name,
            "service_name": traj.service_name,
            "started_at": traj.started_at.isoformat() if traj.started_at else None,
            "assigned_user_id": str(traj.assigned_user_id) if traj.assigned_user_id else None,
            "score": float(score),
            "hit_count": hit_count,
            "hits": [
                {
                    "heuristic": h.heuristic,
                    "severity": h.severity,
                    "signature": h.signature,
                    "details": h.details,
                }
                for h in hits
            ],
        })
    return {"items": items, "total": len(items), "offset": offset, "limit": limit}
```

Register in `main.py`.

- [ ] **Step 4: Pass + commit**

```bash
git add api/app/api/triage.py api/app/main.py api/tests/test_api_triage.py
git commit -m "feat: triage queue API with severity scoring"
```

---

## Task 12: Cluster API

**Files:**
- Create: `api/app/api/clusters.py`
- Modify: `api/app/main.py`
- Create: `api/tests/test_api_clusters.py`

- [ ] **Step 1: Failing test**

```python
async def _bootstrap(client):
    await client.post(
        "/api/auth/signup",
        json={"email": "a@b", "password": "pw12345678", "display_name": "A"},
    )


async def test_clusters_group_trajectories_by_signature(client, session):
    await _bootstrap(client)
    from app.heuristics.engine import evaluate_trajectory
    from app.models import Organization, Span, Trajectory
    from sqlalchemy import select
    org = (await session.execute(select(Organization))).scalar_one()
    for i in range(3):
        t = Trajectory(org_id=org.id, trace_id=f"t{i}", service_name="svc", name=f"n{i}")
        session.add(t); await session.flush()
        session.add(Span(
            span_id=f"s{i}", trace_id=f"t{i}", trajectory_id=t.id, name="search",
            kind="tool", status_code="ERROR",
            attributes={"tool.name": "search"},
            events=[{"name": "exception", "attributes": {"exception.message": "timeout"}}],
        ))
        await session.commit()
        await evaluate_trajectory(session, t.id)

    r = await client.get("/api/clusters")
    body = r.json()
    assert body["clusters"]
    assert body["clusters"][0]["size"] == 3
```

- [ ] **Step 2: Fail.**

- [ ] **Step 3: Implement**

```python
# api/app/api/clusters.py
from collections import defaultdict
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_user
from app.db import get_session
from app.models import HeuristicHit, Trajectory
from app.services.cluster import signature_hash, trajectory_signature

router = APIRouter(prefix="/api/clusters", tags=["clusters"])


@router.get("")
async def list_clusters(
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
    limit: int = 50,
):
    # Collect trajectory → signatures mapping for the org.
    rows = (await session.execute(
        select(HeuristicHit.trajectory_id, HeuristicHit.heuristic, HeuristicHit.signature)
        .where(HeuristicHit.org_id == user.org_id)
    )).all()

    by_traj: dict[str, list[dict]] = defaultdict(list)
    for tid, heuristic, sig in rows:
        by_traj[str(tid)].append({"heuristic": heuristic, "signature": sig})

    sig_to_trajs: dict[str, list[str]] = defaultdict(list)
    for tid, hits in by_traj.items():
        sig = trajectory_signature(hits)
        if not sig:
            continue
        sig_to_trajs[sig].append(tid)

    clusters = sorted(
        (
            {
                "id": signature_hash(sig),
                "signature": sig,
                "heuristics": sig.split("|"),
                "size": len(tids),
                "trajectory_ids": tids[:20],
            }
            for sig, tids in sig_to_trajs.items()
        ),
        key=lambda c: c["size"],
        reverse=True,
    )[:limit]
    return {"clusters": clusters}
```

Register in `main.py`.

- [ ] **Step 4: Pass + commit**

```bash
git add api/app/api/clusters.py api/app/main.py api/tests/test_api_clusters.py
git commit -m "feat: cluster API — group trajectories by heuristic signature"
```

---

## Task 13: Frontend — triage client helpers

**Files:**
- Create: `web/lib/triage.ts`

```ts
import { CLIENT_API_URL, SERVER_API_URL } from "./api";

export type HeuristicHit = {
  heuristic: string;
  severity: number;
  signature: string;
  details: Record<string, unknown>;
};

export type QueueItem = {
  trajectory_id: string;
  name: string;
  service_name: string;
  started_at: string | null;
  assigned_user_id: string | null;
  score: number;
  hit_count: number;
  hits: HeuristicHit[];
};

export type Cluster = {
  id: string;
  signature: string;
  heuristics: string[];
  size: number;
  trajectory_ids: string[];
};

export async function fetchQueue(
  params: { heuristic?: string[]; assigned_to_me?: boolean } = {},
  cookie?: string,
): Promise<{ items: QueueItem[] }> {
  const qs = new URLSearchParams();
  (params.heuristic ?? []).forEach((h) => qs.append("heuristic", h));
  if (params.assigned_to_me) qs.set("assigned_to_me", "true");
  const res = await fetch(`${SERVER_API_URL}/api/queue?${qs}`, {
    headers: cookie ? { cookie } : {},
    cache: "no-store",
  });
  return res.json();
}

export async function fetchClusters(cookie?: string): Promise<{ clusters: Cluster[] }> {
  const res = await fetch(`${SERVER_API_URL}/api/clusters`, {
    headers: cookie ? { cookie } : {},
    cache: "no-store",
  });
  return res.json();
}
```

```bash
git add web/lib/triage.ts
git commit -m "feat: triage client helpers"
```

---

## Task 14: Queue landing page

**Files:**
- Create: `web/app/queue/page.tsx`
- Create: `web/components/queue/queue-row.tsx`
- Create: `web/components/queue/heuristic-badge.tsx`
- Create: `web/components/queue/filter-bar.tsx`

- [ ] **Step 1: Heuristic badge**

```tsx
// web/components/queue/heuristic-badge.tsx
const COLOR: Record<string, string> = {
  tool_error: "bg-warn/20 text-warn",
  latency_outlier: "bg-peach-neon/20 text-peach-neon",
  apology_phrase: "bg-patina/20 text-patina",
  loop: "bg-peach-neon/20 text-peach-neon",
  low_confidence: "bg-warm-fog/20 text-warm-fog",
};

export function HeuristicBadge({ heuristic }: { heuristic: string }) {
  return (
    <span className={`rounded-full px-2 py-0.5 text-[0.65rem] ${COLOR[heuristic] ?? "bg-warm-fog/10 text-warm-fog"}`}>
      {heuristic.replace(/_/g, " ")}
    </span>
  );
}
```

- [ ] **Step 2: Queue row**

```tsx
// web/components/queue/queue-row.tsx
import Link from "next/link";

import type { QueueItem } from "@/lib/triage";
import { HeuristicBadge } from "./heuristic-badge";

export function QueueRow({ item }: { item: QueueItem }) {
  return (
    <Link
      href={`/t/${item.trajectory_id}`}
      className="flex items-start justify-between gap-4 rounded-lg border border-warm-fog/10 p-3 transition hover:border-aether-teal"
    >
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-warm-fog">{item.name || item.service_name}</p>
        <p className="mt-0.5 text-xs text-warm-fog/50">
          {item.service_name} · {item.started_at ? new Date(item.started_at).toLocaleString() : "—"}
        </p>
        <div className="mt-2 flex flex-wrap gap-1">
          {Array.from(new Set(item.hits.map((h) => h.heuristic))).map((h) => (
            <HeuristicBadge key={h} heuristic={h} />
          ))}
        </div>
      </div>
      <div className="shrink-0 text-right">
        <p className="text-sm text-aether-teal">{item.score.toFixed(1)}</p>
        <p className="text-[0.65rem] text-warm-fog/40">score</p>
      </div>
    </Link>
  );
}
```

- [ ] **Step 3: Filter bar**

```tsx
// web/components/queue/filter-bar.tsx
"use client";

import { useRouter, useSearchParams } from "next/navigation";

const HEURISTICS = [
  ["tool_error", "Tool errors"],
  ["latency_outlier", "Latency outliers"],
  ["apology_phrase", "Apologies"],
  ["loop", "Loops"],
  ["low_confidence", "Low confidence"],
] as const;

export function FilterBar() {
  const router = useRouter();
  const params = useSearchParams();
  const active = new Set(params.getAll("heuristic"));

  function toggle(h: string) {
    const next = new Set(active);
    if (next.has(h)) next.delete(h);
    else next.add(h);
    const qs = new URLSearchParams();
    next.forEach((x) => qs.append("heuristic", x));
    router.push(`/queue?${qs.toString()}`);
  }

  return (
    <div className="flex flex-wrap gap-2">
      {HEURISTICS.map(([slug, label]) => (
        <button
          key={slug}
          onClick={() => toggle(slug)}
          className={`rounded-full px-3 py-1 text-xs ring-1 ${
            active.has(slug)
              ? "bg-aether-teal/20 text-aether-teal ring-aether-teal"
              : "bg-warm-fog/5 text-warm-fog/70 ring-warm-fog/20"
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Queue page**

```tsx
// web/app/queue/page.tsx
import { headers } from "next/headers";

import { FilterBar } from "@/components/queue/filter-bar";
import { QueueRow } from "@/components/queue/queue-row";
import { fetchQueue } from "@/lib/triage";

export const dynamic = "force-dynamic";

export default async function QueuePage({
  searchParams,
}: {
  searchParams: { heuristic?: string | string[] };
}) {
  const cookie = headers().get("cookie") ?? "";
  const heuristic = searchParams.heuristic
    ? Array.isArray(searchParams.heuristic)
      ? searchParams.heuristic
      : [searchParams.heuristic]
    : [];
  const { items } = await fetchQueue({ heuristic }, cookie);

  return (
    <main className="space-y-6 p-6">
      <header className="space-y-1">
        <h1 className="text-lg font-semibold text-aether-teal">Triage queue</h1>
        <p className="text-xs text-warm-fog/60">
          Sorted by heuristic severity. Work the top of the list first.
        </p>
      </header>
      <FilterBar />
      <ul className="space-y-2">
        {items.length === 0 ? (
          <li className="rounded-lg border border-dashed border-warm-fog/20 p-6 text-center text-sm text-warm-fog/50">
            Queue is empty — nothing needs review.
          </li>
        ) : (
          items.map((item) => (
            <li key={item.trajectory_id}>
              <QueueRow item={item} />
            </li>
          ))
        )}
      </ul>
    </main>
  );
}
```

- [ ] **Step 5: Update middleware default**

Modify `web/middleware.ts` — when an authed user hits `/`, rewrite to `/queue`:

```ts
if (pathname === "/" && hasSession) {
  const url = request.nextUrl.clone();
  url.pathname = "/queue";
  return NextResponse.redirect(url);
}
```

(Keep dashboard reachable at `/dashboard`.)

- [ ] **Step 6: Commit**

```bash
git add web/app/queue web/components/queue web/middleware.ts
git commit -m "feat: triage queue landing page + filters"
```

---

## Task 15: Clusters view

**Files:**
- Create: `web/app/queue/clusters/page.tsx`
- Create: `web/components/queue/cluster-card.tsx`

- [ ] **Step 1: Cluster card**

```tsx
// web/components/queue/cluster-card.tsx
import Link from "next/link";

import type { Cluster } from "@/lib/triage";
import { HeuristicBadge } from "./heuristic-badge";

export function ClusterCard({ cluster }: { cluster: Cluster }) {
  return (
    <div className="rounded-lg border border-warm-fog/10 p-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-warm-fog">{cluster.size} trajectories share this shape</p>
          <div className="mt-2 flex flex-wrap gap-1">
            {cluster.heuristics.map((h) => (
              <HeuristicBadge key={h} heuristic={h.split(":")[0]} />
            ))}
          </div>
          <p className="mt-1 font-mono text-[0.65rem] text-warm-fog/40">{cluster.signature}</p>
        </div>
        <Link
          href={`/t/${cluster.trajectory_ids[0]}`}
          className="shrink-0 rounded bg-aether-teal/10 px-3 py-1 text-xs text-aether-teal"
        >
          Open first
        </Link>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Cluster page**

```tsx
// web/app/queue/clusters/page.tsx
import { headers } from "next/headers";

import { ClusterCard } from "@/components/queue/cluster-card";
import { fetchClusters } from "@/lib/triage";

export const dynamic = "force-dynamic";

export default async function ClustersPage() {
  const cookie = headers().get("cookie") ?? "";
  const { clusters } = await fetchClusters(cookie);

  return (
    <main className="space-y-6 p-6">
      <header className="space-y-1">
        <h1 className="text-lg font-semibold text-aether-teal">Clusters</h1>
        <p className="text-xs text-warm-fog/60">
          Trajectories grouped by the shape of their heuristic hits. Large clusters = recurring failure.
        </p>
      </header>
      <div className="space-y-2">
        {clusters.length === 0 ? (
          <p className="rounded-lg border border-dashed border-warm-fog/20 p-6 text-center text-sm text-warm-fog/50">
            No clusters yet.
          </p>
        ) : (
          clusters.map((c) => <ClusterCard key={c.id} cluster={c} />)
        )}
      </div>
    </main>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add web/app/queue/clusters web/components/queue
git commit -m "feat: cluster view"
```

---

## Task 16: Nav entry for queue + clusters

**Files:**
- Modify: left nav / sidebar component (discover via `grep -rn "NavRail\|nav-rail" web/components`)

- [ ] **Step 1: Add Queue + Clusters entries as top-level nav items**

Minimal visual addition to the existing nav rail. Add icons + labels in the same style as other entries.

- [ ] **Step 2: Commit**

```bash
git add web/components/shell
git commit -m "feat: queue + clusters nav entries"
```

---

## Task 17: Heuristic hits sidebar on trajectory detail

**Files:**
- Modify: existing trajectory detail right panel or context sidebar

- [ ] **Step 1: Add `hits` fetch on the trajectory page**

Server component fetches `/api/trajectories/:id/hits` (add this endpoint — tiny wrapper around `HeuristicHit` scoped to org + trajectory) and renders a list in the context sidebar.

New endpoint (`api/app/api/triage.py`):

```python
@router.get("/{trajectory_id}/hits", tags=["triage"])
async def hits_for_trajectory(
    trajectory_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    rows = (await session.execute(
        select(HeuristicHit).where(
            HeuristicHit.trajectory_id == trajectory_id, HeuristicHit.org_id == user.org_id
        ).order_by(HeuristicHit.severity.desc())
    )).scalars().all()
    return [
        {
            "heuristic": h.heuristic, "severity": h.severity,
            "signature": h.signature, "details": h.details,
        }
        for h in rows
    ]
```

Note: move this under `/api/trajectories/{id}/hits` path for URL consistency:

```python
router_traj_hits = APIRouter(tags=["triage"])

@router_traj_hits.get("/api/trajectories/{trajectory_id}/hits")
async def hits_for_trajectory(...): ...
```

Register both routers.

- [ ] **Step 2: Render in sidebar**

Use the existing context sidebar pattern to show hits with `<HeuristicBadge />`. Clicking a hit scrolls/highlights the referenced `span_id` via the selection context.

- [ ] **Step 3: Commit**

```bash
git add api/app/api/triage.py api/app/main.py web/components
git commit -m "feat: heuristic hits in trajectory context sidebar"
```

---

## Task 18: Playwright — triage flow

**Files:**
- Create: `web/tests/triage.spec.ts`

```ts
import { expect, test } from "@playwright/test";

test("queue is the default for logged-in users", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/queue/);
});

test("queue row opens trajectory detail", async ({ page }) => {
  await page.goto("/queue");
  const row = page.locator("a[href^='/t/']").first();
  if (await row.isVisible()) {
    await row.click();
    await expect(page).toHaveURL(/\/t\//);
  }
});

test("heuristic filter toggles URL state", async ({ page }) => {
  await page.goto("/queue");
  await page.getByRole("button", { name: /tool errors/i }).click();
  await expect(page).toHaveURL(/heuristic=tool_error/);
});
```

```bash
git add web/tests/triage.spec.ts
git commit -m "tests: playwright triage flow"
```

---

## Notes for the implementer

- **Heuristic tuning** is iterative. The thresholds (`MARGIN = 2.0`, `THRESHOLD = 3`, `MIN_FINAL_OUTPUT_LEN = 10`) are starting points; plan to revisit them once you have real data flowing through. Add telemetry: log the number of hits per heuristic per day so you can see drift.
- **Span attribute keys** assume OTel GenAI semconv (`gen_ai.response.text`, `tool.name`, `tool.arguments`). If your SDK uses different keys, add an adapter in `heuristics/types.py` that normalizes spans before passing to heuristics.
- **Performance**: `evaluate_trajectory` reads every span for the trajectory. That's fine at v2 scale. If trajectories grow to thousands of spans, add streaming or pre-aggregated tool-call summaries.
- **Baseline freshness**: `compute_p95_baselines` reads all spans for the org every evaluation. Memoize per request or pre-compute into a table (`p95_baselines`) nightly if it becomes expensive.
- **Backfill before shipping**: after the migration lands in prod, run `python -m app.cli.backfill_heuristics` to populate hits for existing trajectories. Otherwise the queue will look empty.
- **Queue as landing page**: middleware redirect `/` → `/queue` for authed users is the "queue-first UX" rule from the spec.

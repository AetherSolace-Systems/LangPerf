# V2d — Branched-Rewrite Annotation UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give SMEs a first-class annotation primitive: "from this step onward, here's what the agent should have done." Rewrites are attached to a specific branch-point span on a trajectory, store structured proposed steps (tool calls + final answer) plus free-form rationale, and live in the v2 collab surface alongside comments and failure-mode tags.

**Out of scope (v3):** Exporting rewrites as preference-pair JSONL, auto-generation of training data, fine-tuning integrations. In v2d, rewrites only live inside LangPerf.

**Architecture:** One new model (`Rewrite`) with a nested JSONB list of proposed steps, one migration (0012), CRUD routes under `/api/trajectories/{id}/rewrites`, and a trajectory-detail UI that puts a "Propose rewrite" affordance on every span's right-panel. Rewrites show as a new tab on trajectory detail. Composer is a side-panel with a step-by-step builder (tool vs. final answer).

**Depends on:** v2a (auth, org_id), v2b (collab UX idioms — side panels, right panel integration).

---

## File Structure

**Backend:**
- `api/app/models.py` — add `Rewrite` model
- `api/alembic/versions/0012_rewrites.py` — migration
- `api/app/api/rewrites.py` — CRUD
- `api/app/main.py` — register router
- `api/tests/test_models_rewrite.py`
- `api/tests/test_api_rewrites.py`

**Frontend:**
- `web/lib/rewrites.ts` — client helpers
- `web/components/rewrite/rewrite-composer.tsx` — side-panel builder UI
- `web/components/rewrite/rewrite-step-editor.tsx` — single-step editor (tool call or final answer)
- `web/components/rewrite/rewrite-list.tsx` — list of rewrites on a trajectory
- `web/components/rewrite/rewrite-button.tsx` — "Propose rewrite" affordance for a span
- `web/app/t/[id]/rewrites/page.tsx` — rewrites tab (if trajectory detail uses tabs) OR integrate into existing layout
- `web/tests/rewrite.spec.ts` — Playwright flow

---

## Task 1: Rewrite model + migration

**Files:**
- Modify: `api/app/models.py`
- Create: `api/alembic/versions/0012_rewrites.py`
- Create: `api/tests/test_models_rewrite.py`

- [ ] **Step 1: Failing test**

```python
from app.models import Organization, Rewrite, Trajectory, User


async def test_rewrite_with_proposed_steps(session):
    org = Organization(name="default", slug="default")
    session.add(org); await session.flush()
    u = User(org_id=org.id, email="a@b", password_hash="x", display_name="A")
    t = Trajectory(org_id=org.id, trace_id="t", service_name="svc", name="n")
    session.add_all([u, t]); await session.flush()

    r = Rewrite(
        org_id=org.id,
        trajectory_id=t.id,
        branch_span_id="span-4",
        author_id=u.id,
        rationale="wrong tool — should have searched invoices not orders",
        proposed_steps=[
            {"kind": "tool_call", "tool_name": "search_invoices", "arguments": {"q": "last month"}},
            {"kind": "final_answer", "text": "You had 3 invoices last month totaling $4,500."},
        ],
        status="draft",
    )
    session.add(r)
    await session.commit()
    await session.refresh(r)
    assert r.id is not None
    assert len(r.proposed_steps) == 2
```

- [ ] **Step 2: Fail.**

- [ ] **Step 3: Add model**

```python
class Rewrite(Base):
    __tablename__ = "rewrites"

    id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    trajectory_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("trajectories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    branch_span_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    author_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    proposed_steps: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )
```

- [ ] **Step 4: Migration**

```python
# api/alembic/versions/0012_rewrites.py
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID

revision = "0012_rewrites"
down_revision = "0011_triage_heuristics"


def upgrade() -> None:
    op.create_table(
        "rewrites",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", PgUUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("trajectory_id", PgUUID(as_uuid=True), sa.ForeignKey("trajectories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_span_id", sa.String(255), nullable=False),
        sa.Column("author_id", PgUUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rationale", sa.Text, nullable=False, server_default=""),
        sa.Column("proposed_steps", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_rewrites_trajectory_id", "rewrites", ["trajectory_id"])
    op.create_index("ix_rewrites_branch_span_id", "rewrites", ["branch_span_id"])


def downgrade() -> None:
    op.drop_index("ix_rewrites_branch_span_id", table_name="rewrites")
    op.drop_index("ix_rewrites_trajectory_id", table_name="rewrites")
    op.drop_table("rewrites")
```

- [ ] **Step 5: Pass + commit**

```bash
cd api && pytest tests/test_models_rewrite.py -v
git add api/app/models.py api/alembic/versions/0012_rewrites.py api/tests/test_models_rewrite.py
git commit -m "feat: rewrite model + migration"
```

---

## Task 2: Rewrite CRUD API

**Files:**
- Create: `api/app/api/rewrites.py`
- Modify: `api/app/main.py`
- Create: `api/tests/test_api_rewrites.py`

- [ ] **Step 1: Failing tests**

```python
async def _bootstrap(client):
    await client.post(
        "/api/auth/signup",
        json={"email": "a@b", "password": "pw12345678", "display_name": "A"},
    )


async def _trajectory(session):
    from app.models import Organization, Trajectory
    from sqlalchemy import select
    org = (await session.execute(select(Organization))).scalar_one()
    t = Trajectory(org_id=org.id, trace_id="t", service_name="svc", name="n")
    session.add(t); await session.commit()
    return t


async def test_create_rewrite(client, session):
    await _bootstrap(client)
    t = await _trajectory(session)
    r = await client.post(
        f"/api/trajectories/{t.id}/rewrites",
        json={
            "branch_span_id": "span-4",
            "rationale": "wrong tool",
            "proposed_steps": [
                {"kind": "tool_call", "tool_name": "search_invoices", "arguments": {"q": "x"}},
                {"kind": "final_answer", "text": "here"},
            ],
            "status": "draft",
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["branch_span_id"] == "span-4"
    assert len(r.json()["proposed_steps"]) == 2


async def test_list_rewrites(client, session):
    await _bootstrap(client)
    t = await _trajectory(session)
    await client.post(
        f"/api/trajectories/{t.id}/rewrites",
        json={"branch_span_id": "s1", "rationale": "", "proposed_steps": [], "status": "draft"},
    )
    r = await client.get(f"/api/trajectories/{t.id}/rewrites")
    assert r.status_code == 200
    assert len(r.json()) == 1


async def test_update_rewrite_only_by_author(client, session):
    await _bootstrap(client)
    t = await _trajectory(session)
    created = await client.post(
        f"/api/trajectories/{t.id}/rewrites",
        json={"branch_span_id": "s1", "rationale": "", "proposed_steps": [], "status": "draft"},
    )
    rid = created.json()["id"]
    r = await client.patch(
        f"/api/rewrites/{rid}",
        json={"rationale": "updated", "proposed_steps": [{"kind": "final_answer", "text": "ok"}], "status": "submitted"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "submitted"


async def test_delete_rewrite(client, session):
    await _bootstrap(client)
    t = await _trajectory(session)
    created = await client.post(
        f"/api/trajectories/{t.id}/rewrites",
        json={"branch_span_id": "s1", "rationale": "", "proposed_steps": [], "status": "draft"},
    )
    rid = created.json()["id"]
    r = await client.delete(f"/api/rewrites/{rid}")
    assert r.status_code == 204
```

- [ ] **Step 2: Fail.**

- [ ] **Step 3: Implement**

```python
# api/app/api/rewrites.py
import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_user
from app.db import get_session
from app.models import Rewrite, Trajectory, User

router = APIRouter(tags=["rewrites"])


class ProposedToolCall(BaseModel):
    kind: Literal["tool_call"]
    tool_name: str
    arguments: dict = Field(default_factory=dict)
    reasoning: str | None = None


class ProposedFinalAnswer(BaseModel):
    kind: Literal["final_answer"]
    text: str


ProposedStep = ProposedToolCall | ProposedFinalAnswer


class CreateRewritePayload(BaseModel):
    branch_span_id: str = Field(min_length=1, max_length=255)
    rationale: str = ""
    proposed_steps: list[ProposedStep] = Field(default_factory=list)
    status: Literal["draft", "submitted"] = "draft"


class UpdateRewritePayload(BaseModel):
    rationale: str | None = None
    proposed_steps: list[ProposedStep] | None = None
    status: Literal["draft", "submitted"] | None = None


class RewriteDto(BaseModel):
    id: str
    trajectory_id: str
    branch_span_id: str
    author_id: str
    author_display_name: str
    rationale: str
    proposed_steps: list[dict]
    status: str
    created_at: datetime
    updated_at: datetime


async def _dto(db: AsyncSession, r: Rewrite) -> dict:
    author = await db.get(User, r.author_id)
    return RewriteDto(
        id=str(r.id),
        trajectory_id=str(r.trajectory_id),
        branch_span_id=r.branch_span_id,
        author_id=str(r.author_id),
        author_display_name=author.display_name if author else "unknown",
        rationale=r.rationale,
        proposed_steps=r.proposed_steps,
        status=r.status,
        created_at=r.created_at,
        updated_at=r.updated_at,
    ).model_dump(mode="json")


async def _assert_trajectory(db: AsyncSession, trajectory_id: uuid.UUID, org_id: uuid.UUID) -> Trajectory:
    t = await db.get(Trajectory, trajectory_id)
    if t is None or t.org_id != org_id:
        raise HTTPException(status_code=404, detail="trajectory not found")
    return t


@router.post("/api/trajectories/{trajectory_id}/rewrites", status_code=201)
async def create(
    trajectory_id: uuid.UUID,
    payload: CreateRewritePayload,
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    await _assert_trajectory(session, trajectory_id, user.org_id)
    r = Rewrite(
        org_id=user.org_id,
        trajectory_id=trajectory_id,
        branch_span_id=payload.branch_span_id,
        author_id=user.id,
        rationale=payload.rationale,
        proposed_steps=[s.model_dump() for s in payload.proposed_steps],
        status=payload.status,
    )
    session.add(r)
    await session.commit()
    await session.refresh(r)
    return await _dto(session, r)


@router.get("/api/trajectories/{trajectory_id}/rewrites")
async def list_for_trajectory(
    trajectory_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    await _assert_trajectory(session, trajectory_id, user.org_id)
    rows = (await session.execute(
        select(Rewrite)
        .where(Rewrite.trajectory_id == trajectory_id)
        .order_by(Rewrite.created_at.desc())
    )).scalars().all()
    return [await _dto(session, r) for r in rows]


@router.get("/api/rewrites/{rewrite_id}")
async def get_one(
    rewrite_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    r = await session.get(Rewrite, rewrite_id)
    if r is None or r.org_id != user.org_id:
        raise HTTPException(status_code=404, detail="not found")
    return await _dto(session, r)


@router.patch("/api/rewrites/{rewrite_id}")
async def update(
    rewrite_id: uuid.UUID,
    payload: UpdateRewritePayload,
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    r = await session.get(Rewrite, rewrite_id)
    if r is None or r.org_id != user.org_id:
        raise HTTPException(status_code=404, detail="not found")
    if r.author_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="only the author can update")
    if payload.rationale is not None:
        r.rationale = payload.rationale
    if payload.proposed_steps is not None:
        r.proposed_steps = [s.model_dump() for s in payload.proposed_steps]
    if payload.status is not None:
        r.status = payload.status
    await session.commit()
    await session.refresh(r)
    return await _dto(session, r)


@router.delete("/api/rewrites/{rewrite_id}", status_code=204)
async def delete(
    rewrite_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    r = await session.get(Rewrite, rewrite_id)
    if r is None or r.org_id != user.org_id:
        raise HTTPException(status_code=404, detail="not found")
    if r.author_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="not allowed")
    await session.delete(r)
    await session.commit()
    return Response(status_code=204)
```

Register in `main.py`:

```python
from app.api import rewrites as rewrites_api
app.include_router(rewrites_api.router)
```

- [ ] **Step 4: Pass + commit**

```bash
cd api && pytest tests/test_api_rewrites.py -v
git add api/app/api/rewrites.py api/app/main.py api/tests/test_api_rewrites.py
git commit -m "feat: rewrite CRUD endpoints"
```

---

## Task 3: Frontend — rewrite client helpers

**Files:**
- Create: `web/lib/rewrites.ts`

```ts
import { CLIENT_API_URL, SERVER_API_URL } from "./api";

export type ProposedStep =
  | { kind: "tool_call"; tool_name: string; arguments: Record<string, unknown>; reasoning?: string }
  | { kind: "final_answer"; text: string };

export type Rewrite = {
  id: string;
  trajectory_id: string;
  branch_span_id: string;
  author_id: string;
  author_display_name: string;
  rationale: string;
  proposed_steps: ProposedStep[];
  status: "draft" | "submitted";
  created_at: string;
  updated_at: string;
};

export async function listRewrites(trajectoryId: string, cookie?: string): Promise<Rewrite[]> {
  const res = await fetch(`${SERVER_API_URL}/api/trajectories/${trajectoryId}/rewrites`, {
    headers: cookie ? { cookie } : {},
    cache: "no-store",
  });
  return res.json();
}

export async function createRewrite(
  trajectoryId: string,
  payload: {
    branch_span_id: string;
    rationale: string;
    proposed_steps: ProposedStep[];
    status: "draft" | "submitted";
  },
): Promise<Rewrite> {
  const res = await fetch(`${CLIENT_API_URL}/api/trajectories/${trajectoryId}/rewrites`, {
    method: "POST",
    credentials: "include",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`createRewrite ${res.status}`);
  return res.json();
}

export async function updateRewrite(
  id: string,
  payload: Partial<{
    rationale: string;
    proposed_steps: ProposedStep[];
    status: "draft" | "submitted";
  }>,
): Promise<Rewrite> {
  const res = await fetch(`${CLIENT_API_URL}/api/rewrites/${id}`, {
    method: "PATCH",
    credentials: "include",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  return res.json();
}

export async function deleteRewrite(id: string): Promise<void> {
  await fetch(`${CLIENT_API_URL}/api/rewrites/${id}`, {
    method: "DELETE",
    credentials: "include",
  });
}
```

```bash
git add web/lib/rewrites.ts
git commit -m "feat: rewrite client helpers"
```

---

## Task 4: Step editor component

**Files:**
- Create: `web/components/rewrite/rewrite-step-editor.tsx`

```tsx
// web/components/rewrite/rewrite-step-editor.tsx
"use client";

import type { ProposedStep } from "@/lib/rewrites";

export function RewriteStepEditor({
  step,
  onChange,
  onRemove,
}: {
  step: ProposedStep;
  onChange: (next: ProposedStep) => void;
  onRemove: () => void;
}) {
  return (
    <div className="space-y-2 rounded-lg bg-warm-fog/5 p-3 ring-1 ring-warm-fog/10">
      <div className="flex items-center justify-between">
        <select
          value={step.kind}
          onChange={(e) => {
            const next: ProposedStep =
              e.target.value === "tool_call"
                ? { kind: "tool_call", tool_name: "", arguments: {} }
                : { kind: "final_answer", text: "" };
            onChange(next);
          }}
          className="rounded bg-carbon px-2 py-1 text-xs text-warm-fog"
        >
          <option value="tool_call">Tool call</option>
          <option value="final_answer">Final answer</option>
        </select>
        <button onClick={onRemove} className="text-xs text-warn">
          Remove
        </button>
      </div>

      {step.kind === "tool_call" ? (
        <>
          <input
            value={step.tool_name}
            onChange={(e) => onChange({ ...step, tool_name: e.target.value })}
            placeholder="tool_name (e.g. search_invoices)"
            className="w-full rounded bg-carbon px-2 py-1 text-xs text-warm-fog"
          />
          <textarea
            value={JSON.stringify(step.arguments, null, 2)}
            onChange={(e) => {
              try {
                onChange({ ...step, arguments: JSON.parse(e.target.value) });
              } catch {
                /* keep user's in-progress text; do not crash */
              }
            }}
            rows={4}
            className="w-full resize-none rounded bg-carbon px-2 py-1 font-mono text-[0.65rem] text-warm-fog"
            placeholder='{"q": "last month"}'
          />
        </>
      ) : (
        <textarea
          value={step.text}
          onChange={(e) => onChange({ ...step, text: e.target.value })}
          rows={4}
          placeholder="What the agent should have said"
          className="w-full resize-none rounded bg-carbon px-2 py-1 text-xs text-warm-fog"
        />
      )}
    </div>
  );
}
```

```bash
git add web/components/rewrite
git commit -m "feat: rewrite step editor"
```

---

## Task 5: Composer + list

**Files:**
- Create: `web/components/rewrite/rewrite-composer.tsx`
- Create: `web/components/rewrite/rewrite-list.tsx`
- Create: `web/components/rewrite/rewrite-button.tsx`

- [ ] **Step 1: Composer**

```tsx
// web/components/rewrite/rewrite-composer.tsx
"use client";

import { useState } from "react";

import { createRewrite, type ProposedStep, type Rewrite } from "@/lib/rewrites";
import { RewriteStepEditor } from "./rewrite-step-editor";

export function RewriteComposer({
  trajectoryId,
  branchSpanId,
  onCreated,
  onCancel,
}: {
  trajectoryId: string;
  branchSpanId: string;
  onCreated: (r: Rewrite) => void;
  onCancel: () => void;
}) {
  const [rationale, setRationale] = useState("");
  const [steps, setSteps] = useState<ProposedStep[]>([
    { kind: "tool_call", tool_name: "", arguments: {} },
  ]);
  const [pending, setPending] = useState(false);

  async function save(status: "draft" | "submitted") {
    setPending(true);
    try {
      const r = await createRewrite(trajectoryId, {
        branch_span_id: branchSpanId,
        rationale,
        proposed_steps: steps,
        status,
      });
      onCreated(r);
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="flex flex-col gap-4 rounded-xl bg-warm-fog/5 p-4 ring-1 ring-aether-teal/30">
      <header>
        <p className="text-xs uppercase tracking-wide text-aether-teal">Propose rewrite</p>
        <p className="text-[0.65rem] text-warm-fog/50">Branch point: {branchSpanId}</p>
      </header>
      <textarea
        value={rationale}
        onChange={(e) => setRationale(e.target.value)}
        placeholder="Why was the agent wrong here?"
        rows={3}
        className="w-full resize-none rounded-lg bg-carbon px-3 py-2 text-sm text-warm-fog"
      />
      <div className="space-y-2">
        {steps.map((s, i) => (
          <RewriteStepEditor
            key={i}
            step={s}
            onChange={(next) => setSteps((prev) => prev.map((x, j) => (j === i ? next : x)))}
            onRemove={() => setSteps((prev) => prev.filter((_, j) => j !== i))}
          />
        ))}
        <button
          onClick={() => setSteps((prev) => [...prev, { kind: "tool_call", tool_name: "", arguments: {} }])}
          className="rounded bg-warm-fog/10 px-3 py-1 text-xs text-warm-fog"
        >
          + Step
        </button>
      </div>
      <div className="flex justify-end gap-2">
        <button onClick={onCancel} className="rounded px-3 py-1 text-xs text-warm-fog/60">
          Cancel
        </button>
        <button
          onClick={() => save("draft")}
          disabled={pending}
          className="rounded bg-warm-fog/10 px-3 py-1 text-xs text-warm-fog disabled:opacity-50"
        >
          Save draft
        </button>
        <button
          onClick={() => save("submitted")}
          disabled={pending}
          className="rounded bg-aether-teal px-3 py-1 text-xs font-semibold text-carbon disabled:opacity-50"
        >
          {pending ? "Saving…" : "Submit"}
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: List**

```tsx
// web/components/rewrite/rewrite-list.tsx
import type { Rewrite } from "@/lib/rewrites";

export function RewriteList({ rewrites }: { rewrites: Rewrite[] }) {
  if (!rewrites.length) {
    return (
      <p className="rounded-lg border border-dashed border-warm-fog/20 p-4 text-center text-xs text-warm-fog/50">
        No rewrites yet. Pick a span in the trajectory and propose one.
      </p>
    );
  }
  return (
    <ul className="space-y-3">
      {rewrites.map((r) => (
        <li key={r.id} className="rounded-lg border border-warm-fog/10 p-3">
          <div className="flex items-center justify-between text-xs">
            <span className="font-medium text-aether-teal">{r.author_display_name}</span>
            <span
              className={`rounded-full px-2 py-0.5 text-[0.65rem] ${
                r.status === "submitted" ? "bg-aether-teal/20 text-aether-teal" : "bg-warm-fog/10 text-warm-fog/60"
              }`}
            >
              {r.status}
            </span>
          </div>
          <p className="mt-1 text-[0.65rem] text-warm-fog/40">Branch: {r.branch_span_id}</p>
          {r.rationale && <p className="mt-2 whitespace-pre-wrap text-sm text-warm-fog">{r.rationale}</p>}
          <ol className="mt-2 space-y-1 text-xs">
            {r.proposed_steps.map((s, i) => (
              <li key={i} className="rounded bg-warm-fog/5 p-2">
                {s.kind === "tool_call" ? (
                  <>
                    <span className="font-mono text-aether-teal">{s.tool_name}</span>
                    <pre className="mt-1 text-[0.65rem] text-warm-fog/70">{JSON.stringify(s.arguments, null, 2)}</pre>
                  </>
                ) : (
                  <p className="text-warm-fog">{s.text}</p>
                )}
              </li>
            ))}
          </ol>
        </li>
      ))}
    </ul>
  );
}
```

- [ ] **Step 3: Rewrite button**

```tsx
// web/components/rewrite/rewrite-button.tsx
"use client";

import { useState } from "react";

import type { Rewrite } from "@/lib/rewrites";
import { RewriteComposer } from "./rewrite-composer";

export function RewriteButton({
  trajectoryId,
  spanId,
  onCreated,
}: {
  trajectoryId: string;
  spanId: string;
  onCreated: (r: Rewrite) => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="rounded bg-aether-teal/10 px-2 py-1 text-xs text-aether-teal"
      >
        Propose rewrite
      </button>
      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-end bg-black/60" onClick={() => setOpen(false)}>
          <div
            onClick={(e) => e.stopPropagation()}
            className="h-full w-[28rem] overflow-y-auto bg-carbon p-4"
          >
            <RewriteComposer
              trajectoryId={trajectoryId}
              branchSpanId={spanId}
              onCreated={(r) => {
                onCreated(r);
                setOpen(false);
              }}
              onCancel={() => setOpen(false)}
            />
          </div>
        </div>
      )}
    </>
  );
}
```

```bash
git add web/components/rewrite
git commit -m "feat: rewrite composer + list + button"
```

---

## Task 6: Wire into trajectory detail

**Files:**
- Modify: existing trajectory detail page at `web/app/t/[id]/page.tsx` (or `web/app/r/[run_id]/page.tsx`)
- Modify: the right panel that currently shows per-span details (discover via `grep -rn "right-panel\|RightPanel\|NodeDetail" web/components`)

- [ ] **Step 1: Fetch rewrites server-side**

In the trajectory detail page, add:

```tsx
import { listRewrites } from "@/lib/rewrites";

// inside the server component
const cookie = headers().get("cookie") ?? undefined;
const rewrites = await listRewrites(params.id, cookie);
```

Pass `rewrites` down to a client wrapper component that can show them in a new "Rewrites" section (below Comments in the right panel, or as a dedicated tab if the detail page uses tabs).

- [ ] **Step 2: Add `RewriteButton` to the span detail**

In the right panel that shows a selected span, render `<RewriteButton trajectoryId={...} spanId={selected.spanId} onCreated={...} />` alongside the comment thread.

- [ ] **Step 3: Add `RewriteList` to the trajectory detail**

Below or tabbed with comments, render `<RewriteList rewrites={rewrites} />`.

- [ ] **Step 4: Commit**

```bash
git add web/app web/components
git commit -m "feat: rewrite UI on trajectory detail"
```

---

## Task 7: Playwright — rewrite flow

**Files:**
- Create: `web/tests/rewrite.spec.ts`

```ts
import { expect, test } from "@playwright/test";

test("propose a rewrite from a span", async ({ page }) => {
  await page.goto("/queue");
  const row = page.locator("a[href^='/t/']").first();
  if (!(await row.isVisible())) test.skip(true, "no trajectories in dev DB");
  await row.click();
  await page.locator("[data-testid^='tree-node-']").first().click();

  await page.getByRole("button", { name: /propose rewrite/i }).click();
  await page.getByPlaceholder(/why was the agent wrong/i).fill(`auto-test ${Date.now()}`);
  await page.getByPlaceholder(/tool_name/i).fill("search_invoices");
  await page.getByRole("button", { name: /^Submit$/ }).click();

  await expect(page.getByText("submitted").first()).toBeVisible();
});
```

```bash
git add web/tests/rewrite.spec.ts
git commit -m "tests: playwright rewrite flow"
```

---

## Notes for the implementer

- **No export in v2d**: rewrites live in LangPerf only. Treat this plan's data model as the authoritative shape v3 will export from — don't embed formatting assumptions that a JSONL generator can't easily lift.
- **Step shape is a discriminated union**: `kind: "tool_call" | "final_answer"`. Keep it that way to make the v3 export simple (map each kind to preference-pair fields separately).
- **Right-panel integration**: the existing per-span right panel is the single integration point for both v2b comments and v2d rewrites. If it's getting crowded, split it into sub-tabs (Comments / Rewrites / Attributes) before both land; a refactor to do that is in-scope here if needed.
- **Reasoning field on tool_call** is optional — SMEs who want to annotate *why* a tool call should have been different can use it; otherwise leave it blank.

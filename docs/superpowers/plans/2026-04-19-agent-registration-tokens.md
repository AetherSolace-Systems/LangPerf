# Per-Agent API Tokens — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Replace auto-detection of agents with explicit registration + per-agent API tokens. OTLP ingest requires a valid bearer token. SDK attaches the token as `Authorization: Bearer`.

**Architecture:**
- `agents` table gains `token_hash` (bcrypt), `token_prefix` (display), `last_token_used_at`, `created_by_user_id`.
- New `/api/agents` POST creates agent + mints token; `/rotate-token` mints new; `/issue-token` bootstraps legacy (tokenless) agents.
- OTLP receiver becomes auth-gated: no valid token → 401. Token's agent_id overrides `service.name`.
- Web: `/agents` becomes sortable/filterable table; modal flow for registration; row actions for rotate/delete/issue.
- SDK: `LANGPERF_API_TOKEN` env var (or `api_token` kwarg) attached as Bearer header on OTLP exporter.

**Tech:** FastAPI + async SQLAlchemy 2.0 + Alembic, bcrypt for hashing, Next.js 14 server components + client modals, OpenTelemetry Python exporter headers.

**Breaking change posture:** Old auto-detected agents keep their historical data but cannot accept new traces until the user clicks "issue token" on each (one-click per-agent). Documented in SDK README upgrade notes.

---

## File structure

**API (new):**
- `api/alembic/versions/0015_agent_tokens.py` — migration
- `api/app/auth/agent_token.py` — token gen/verify helpers
- `api/tests/test_agent_token_helpers.py`
- `api/tests/test_api_agents_crud.py`
- `api/tests/test_otlp_auth.py`

**API (modify):**
- `api/app/models.py` — Agent fields
- `api/app/api/agents.py` — add POST, rotate, issue-token, DELETE; update GET to expose token_prefix + last_used
- `api/app/otlp/receiver.py` — bearer extraction + verification
- `api/app/otlp/agent_resolver.py` — remove auto-create; only resolve by token's agent_id
- `api/app/ingest/org.py` — keep as-is (default org still needed)

**Web (new):**
- `web/components/agents/agents-table.tsx`
- `web/components/agents/new-agent-modal.tsx`
- `web/components/agents/token-display.tsx`
- `web/components/agents/row-actions.tsx`
- `web/lib/agents.ts`

**Web (modify):**
- `web/app/agents/page.tsx` — rewrite grid → table
- `web/lib/api.ts` — extend AgentSummary + AgentDetail types with token_prefix, last_token_used_at

**SDK (modify):**
- `sdk/langperf/tracer.py` — accept token, inject headers
- `sdk/README.md` — document the env var + migration note

**Cleanup:**
- `web/components/shell/nav-config.ts` — remove `sdk-keys` entry

---

## Token format

`lp_<8char>_<32char>` (e.g. `lp_a1b2c3d4_xXx…`). First 11 chars = prefix; stored as-is + indexed. Whole string bcrypt-hashed. Show once.

Prefix collisions: vanishingly rare at dogfood scale; we generate until unique (2 retries max, 500 on exhaustion).

---

## Task 1 — Migration 0015: agent token fields

**Files:**
- Create: `api/alembic/versions/0015_agent_tokens.py`

**Steps:**

- [ ] **Step 1: Write the migration**

```python
"""agent tokens

Revision ID: 0015_agent_tokens
Revises: 0014_updated_tagged_defaults
Create Date: 2026-04-19 00:00:00.000000
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision = "0015_agent_tokens"
down_revision = "0014_updated_tagged_defaults"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("token_hash", sa.String(255), nullable=True))
    op.add_column("agents", sa.Column("token_prefix", sa.String(24), nullable=True))
    op.add_column("agents", sa.Column("last_token_used_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "agents",
        sa.Column(
            "created_by_user_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_agents_token_prefix", "agents", ["token_prefix"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_agents_token_prefix", table_name="agents")
    op.drop_column("agents", "created_by_user_id")
    op.drop_column("agents", "last_token_used_at")
    op.drop_column("agents", "token_prefix")
    op.drop_column("agents", "token_hash")
```

- [ ] **Step 2: Update Agent model**

Edit `api/app/models.py`, class `Agent`. After existing fields, add:

```python
    token_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    token_prefix: Mapped[str | None] = mapped_column(String(24), nullable=True, unique=True, index=True)
    last_token_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[str | None] = mapped_column(
        UUIDStr,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
```

- [ ] **Step 3: Apply + verify against the running Postgres**

```
docker compose exec langperf-api alembic upgrade head
docker compose exec postgres psql -U langperf -d langperf -c "\d agents"
```

Expect the four new columns + `ix_agents_token_prefix` index.

- [ ] **Step 4: Commit**

```
git add api/alembic/versions/0015_agent_tokens.py api/app/models.py
git commit -m "feat(agents): add token fields + index for per-agent auth"
```

---

## Task 2 — Token helpers

**Files:**
- Create: `api/app/auth/agent_token.py`
- Create: `api/tests/test_agent_token_helpers.py`

**Steps:**

- [ ] **Step 1: Write the failing test**

`api/tests/test_agent_token_helpers.py`:

```python
import pytest

from app.auth.agent_token import (
    TOKEN_PREFIX_LEN,
    generate_token,
    hash_token,
    verify_token,
)


def test_generate_token_shape():
    token, prefix = generate_token()
    assert token.startswith("lp_")
    # lp_ + 8-char id + _ + 32-char random
    assert len(token) == 3 + 8 + 1 + 32
    assert token[:TOKEN_PREFIX_LEN] == prefix
    assert len(prefix) == TOKEN_PREFIX_LEN


def test_hash_and_verify_roundtrip():
    token, _ = generate_token()
    digest = hash_token(token)
    assert verify_token(token, digest) is True
    assert verify_token(token + "x", digest) is False


def test_generate_token_is_unique():
    seen = set()
    for _ in range(50):
        t, _ = generate_token()
        assert t not in seen
        seen.add(t)
```

- [ ] **Step 2: Run, expect ImportError / module missing**

`cd api && .venv/bin/python -m pytest tests/test_agent_token_helpers.py -v`

- [ ] **Step 3: Implement helpers**

`api/app/auth/agent_token.py`:

```python
"""Per-agent API token generation + verification.

Tokens are `lp_<8-char-id>_<32-char-random>`. The first 12 characters
(`lp_<8-char-id>`) are the prefix — stored in plaintext on the row, used
to find the agent at auth time. The whole token is bcrypt-hashed for
storage. The raw token is returned once at creation/rotation; after
that only the prefix is displayable.
"""

from __future__ import annotations

import secrets

import bcrypt

TOKEN_PREFIX_LEN = 12  # "lp_" + 8 chars
_ID_ALPHABET = "abcdefghijkmnopqrstuvwxyz23456789"  # no 0/o/1/l to reduce confusion
_RANDOM_LEN = 32


def _random_id(length: int) -> str:
    return "".join(secrets.choice(_ID_ALPHABET) for _ in range(length))


def generate_token() -> tuple[str, str]:
    """Return (raw_token, prefix)."""
    short = _random_id(8)
    random = _random_id(_RANDOM_LEN)
    token = f"lp_{short}_{random}"
    prefix = token[:TOKEN_PREFIX_LEN]
    return token, prefix


def hash_token(raw: str) -> str:
    return bcrypt.hashpw(raw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_token(raw: str, digest: str) -> bool:
    try:
        return bcrypt.checkpw(raw.encode("utf-8"), digest.encode("utf-8"))
    except (ValueError, TypeError):
        return False
```

- [ ] **Step 4: Run test suite**

`cd api && .venv/bin/python -m pytest tests/test_agent_token_helpers.py -v` — expect 3 passed.

- [ ] **Step 5: Commit**

```
git add api/app/auth/agent_token.py api/tests/test_agent_token_helpers.py
git commit -m "feat(agents): token generation + bcrypt verify helpers"
```

---

## Task 3 — Agent CRUD API (create, rotate, issue, delete)

**Files:**
- Modify: `api/app/api/agents.py`
- Create: `api/tests/test_api_agents_crud.py`

**Signature for registered agents:** `registered:<uuid4>` — keeps the unique constraint satisfied without colliding with SDK-ingested `sig:<hash>` signatures.

**Steps:**

- [ ] **Step 1: Write the failing test**

`api/tests/test_api_agents_crud.py`:

```python
import pytest


async def _bootstrap(client):
    r = await client.post(
        "/api/auth/signup",
        json={"email": "a@b.co", "password": "pw-12345678", "display_name": "A"},
    )
    assert r.status_code == 201


async def test_create_agent_returns_token_once(client):
    await _bootstrap(client)
    r = await client.post(
        "/api/agents",
        json={"name": "weather-bot", "language": "python", "description": "demo"},
    )
    assert r.status_code == 201
    body = r.json()
    assert "token" in body
    assert body["token"].startswith("lp_")
    assert body["agent"]["name"] == "weather-bot"
    assert body["agent"]["token_prefix"] is not None
    assert body["agent"]["token_prefix"] == body["token"][:12]

    # Token is only shown once
    listed = (await client.get("/api/agents")).json()
    row = next(a for a in listed if a["name"] == "weather-bot")
    assert "token" not in row
    assert row["token_prefix"] == body["token"][:12]


async def test_create_agent_rejects_duplicate_name(client):
    await _bootstrap(client)
    await client.post("/api/agents", json={"name": "dup", "language": "python"})
    r = await client.post("/api/agents", json={"name": "dup", "language": "python"})
    assert r.status_code == 409


async def test_rotate_token_changes_prefix(client):
    await _bootstrap(client)
    r1 = await client.post("/api/agents", json={"name": "rot", "language": "python"})
    first_prefix = r1.json()["token"][:12]
    r2 = await client.post("/api/agents/rot/rotate-token")
    assert r2.status_code == 200
    second = r2.json()
    assert second["token"].startswith("lp_")
    assert second["token"][:12] != first_prefix


async def test_issue_token_on_legacy_agent(client, session):
    await _bootstrap(client)
    from app.models import Agent, Organization
    from sqlalchemy import select
    org = (await session.execute(select(Organization))).scalar_one()
    session.add(Agent(org_id=org.id, signature="legacy:x", name="legacy-bot"))
    await session.commit()

    r = await client.post("/api/agents/legacy-bot/issue-token")
    assert r.status_code == 200
    assert r.json()["token"].startswith("lp_")


async def test_issue_token_rejects_if_already_has_token(client):
    await _bootstrap(client)
    await client.post("/api/agents", json={"name": "has-token", "language": "python"})
    r = await client.post("/api/agents/has-token/issue-token")
    assert r.status_code == 409


async def test_delete_agent(client):
    await _bootstrap(client)
    await client.post("/api/agents", json={"name": "byebye", "language": "python"})
    r = await client.delete("/api/agents/byebye")
    assert r.status_code == 204
    assert (await client.get("/api/agents/byebye")).status_code == 404
```

- [ ] **Step 2: Run, expect failures** (endpoints don't exist yet).

- [ ] **Step 3: Implement endpoints**

Edit `api/app/api/agents.py`. Add imports at the top alongside existing ones:

```python
import uuid as _uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status

from app.auth.agent_token import generate_token, hash_token
```

Add new endpoint handlers (location: after existing GET /api/agents; before GET /api/agents/{name}):

```python
class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")
    display_name: str | None = None
    description: str | None = None
    language: str | None = None
    github_url: str | None = None


@router.post("", status_code=201)
async def create_agent(
    payload: AgentCreate,
    session: AsyncSession = Depends(get_session),
    user=require_user(),
) -> dict:
    existing = (
        await session.execute(select(Agent).where(Agent.org_id == user.org_id, Agent.name == payload.name))
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"agent {payload.name!r} already exists")
    token, prefix = generate_token()
    agent = Agent(
        org_id=user.org_id,
        signature=f"registered:{_uuid.uuid4()}",
        name=payload.name,
        display_name=payload.display_name,
        description=payload.description,
        language=payload.language,
        github_url=payload.github_url,
        token_hash=hash_token(token),
        token_prefix=prefix,
        created_by_user_id=user.id,
    )
    session.add(agent)
    await session.commit()
    await session.refresh(agent)
    return {"agent": _agent_to_dict(agent), "token": token}


@router.post("/{name}/rotate-token")
async def rotate_token(
    name: str,
    session: AsyncSession = Depends(get_session),
    user=require_user(),
) -> dict:
    agent = (
        await session.execute(select(Agent).where(Agent.org_id == user.org_id, Agent.name == name))
    ).scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="agent not found")
    token, prefix = generate_token()
    agent.token_hash = hash_token(token)
    agent.token_prefix = prefix
    agent.last_token_used_at = None
    await session.commit()
    return {"token": token, "token_prefix": prefix}


@router.post("/{name}/issue-token")
async def issue_token(
    name: str,
    session: AsyncSession = Depends(get_session),
    user=require_user(),
) -> dict:
    agent = (
        await session.execute(select(Agent).where(Agent.org_id == user.org_id, Agent.name == name))
    ).scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="agent not found")
    if agent.token_hash is not None:
        raise HTTPException(status_code=409, detail="agent already has a token; rotate instead")
    token, prefix = generate_token()
    agent.token_hash = hash_token(token)
    agent.token_prefix = prefix
    await session.commit()
    return {"token": token, "token_prefix": prefix}


@router.delete("/{name}", status_code=204)
async def delete_agent(
    name: str,
    session: AsyncSession = Depends(get_session),
    user=require_user(),
) -> None:
    agent = (
        await session.execute(select(Agent).where(Agent.org_id == user.org_id, Agent.name == name))
    ).scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="agent not found")
    await session.delete(agent)
    await session.commit()
```

Ensure `_agent_to_dict` includes `token_prefix` and `last_token_used_at`. If the existing GET handler builds dicts inline, extract the serialization to a helper (`_agent_to_dict`) and use it from both old and new handlers.

- [ ] **Step 4: Run full api tests**

`cd api && .venv/bin/python -m pytest -x -q` — expect all green.

- [ ] **Step 5: Commit**

```
git add api/app/api/agents.py api/tests/test_api_agents_crud.py
git commit -m "feat(agents): create/rotate/issue-token/delete endpoints"
```

---

## Task 4 — OTLP ingest: require bearer token

**Files:**
- Modify: `api/app/otlp/receiver.py`
- Modify: `api/app/otlp/agent_resolver.py` (remove auto-create path)
- Create: `api/tests/test_otlp_auth.py`

**Steps:**

- [ ] **Step 1: Write the failing test**

`api/tests/test_otlp_auth.py`:

```python
async def test_otlp_rejects_missing_bearer(client):
    r = await client.post("/v1/traces", content=b"\x00", headers={"content-type": "application/x-protobuf"})
    assert r.status_code == 401


async def test_otlp_rejects_unknown_token(client):
    r = await client.post(
        "/v1/traces",
        content=b"\x00",
        headers={
            "content-type": "application/x-protobuf",
            "authorization": "Bearer lp_aaaaaaaa_notarealtokeneverxyz",
        },
    )
    assert r.status_code == 401


async def test_otlp_accepts_valid_token_and_binds(client, session):
    # bootstrap + create agent
    await client.post(
        "/api/auth/signup",
        json={"email": "a@b.co", "password": "pw-12345678", "display_name": "A"},
    )
    r = await client.post("/api/agents", json={"name": "dog", "language": "python"})
    token = r.json()["token"]

    # minimal well-formed protobuf would be ideal; for this auth-level test a
    # trivially-empty request that passes past auth and fails parsing is OK —
    # 400 from the parser still proves auth succeeded.
    r2 = await client.post(
        "/v1/traces",
        content=b"",
        headers={"content-type": "application/x-protobuf", "authorization": f"Bearer {token}"},
    )
    assert r2.status_code != 401  # passed auth
```

- [ ] **Step 2: Run, expect failures**

- [ ] **Step 3: Implement auth in receiver**

Edit `api/app/otlp/receiver.py`. At the top:

```python
from fastapi import Header, HTTPException, status

from app.auth.agent_token import TOKEN_PREFIX_LEN, verify_token
from app.models import Agent
```

Replace the current handler signature + prelude with:

```python
@router.post("/v1/traces")
async def receive_traces(
    request: Request,
    content_type: str | None = Header(default=None, alias="content-type"),
    authorization: str | None = Header(default=None, alias="authorization"),
    session: AsyncSession = Depends(get_session),
):
    token = _extract_bearer(authorization)
    if token is None:
        raise HTTPException(status_code=401, detail="bearer token required")
    agent = await _resolve_agent_by_token(session, token)
    if agent is None:
        raise HTTPException(status_code=401, detail="invalid token")
    # existing body: parse request body, resolve via agent_id bound to `agent`
    # downstream resolver receives the auth-verified agent_id
    ...
```

Add helpers at module bottom:

```python
def _extract_bearer(header: str | None) -> str | None:
    if not header:
        return None
    parts = header.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


async def _resolve_agent_by_token(session: AsyncSession, token: str) -> Agent | None:
    prefix = token[:TOKEN_PREFIX_LEN]
    row = (
        await session.execute(select(Agent).where(Agent.token_prefix == prefix))
    ).scalar_one_or_none()
    if row is None or row.token_hash is None:
        return None
    if not verify_token(token, row.token_hash):
        return None
    return row
```

Update the agent resolver to use the auth-verified `agent` instead of signature-based lookup:

In `api/app/otlp/agent_resolver.py`, change `resolve_agent_and_version` to take an `agent_id` argument (already authoritative) and only resolve the *version* part (version still comes from span attributes). Remove the auto-create `_upsert_agent` path.

After span parsing, bump `agent.last_token_used_at = datetime.now(timezone.utc)` (fire-and-forget OK — commit with the rest of the ingest transaction).

- [ ] **Step 4: Run tests**

`cd api && .venv/bin/python -m pytest -x -q`

- [ ] **Step 5: Commit**

```
git add api/app/otlp/ api/tests/test_otlp_auth.py
git commit -m "feat(otlp): require bearer token, drop auto-create agent path"
```

---

## Task 5 — Web: agents table + registration modal

**Files:**
- Create: `web/lib/agents.ts`
- Create: `web/components/agents/agents-table.tsx`
- Create: `web/components/agents/new-agent-modal.tsx`
- Create: `web/components/agents/token-display.tsx`
- Create: `web/components/agents/row-actions.tsx`
- Modify: `web/app/agents/page.tsx`
- Modify: `web/lib/api.ts` — extend types

**Steps:**

- [ ] **Step 1: Extend agent types**

Edit `web/lib/api.ts`:

```ts
export type AgentSummary = {
  id: string;
  name: string;
  display_name: string | null;
  description: string | null;
  owner: string | null;
  github_url: string | null;
  language: string | null;
  token_prefix: string | null;
  last_token_used_at: string | null;
  created_at: string;
  updated_at: string;
};
```

Add the two optional fields to any existing `AgentSummary`/detail types.

- [ ] **Step 2: Create `web/lib/agents.ts`**

```ts
import { apiBase } from "./api";

export type CreateAgentPayload = {
  name: string;
  display_name?: string;
  description?: string;
  language?: string;
  github_url?: string;
};

export async function createAgent(payload: CreateAgentPayload): Promise<{ agent: any; token: string }> {
  const res = await fetch(`${apiBase()}/api/agents`, {
    method: "POST",
    credentials: "include",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "create failed" }));
    throw new Error(body.detail ?? `createAgent ${res.status}`);
  }
  return res.json();
}

export async function rotateAgentToken(name: string): Promise<{ token: string; token_prefix: string }> {
  const res = await fetch(`${apiBase()}/api/agents/${encodeURIComponent(name)}/rotate-token`, {
    method: "POST",
    credentials: "include",
  });
  if (!res.ok) throw new Error(`rotateAgentToken ${res.status}`);
  return res.json();
}

export async function issueAgentToken(name: string): Promise<{ token: string; token_prefix: string }> {
  const res = await fetch(`${apiBase()}/api/agents/${encodeURIComponent(name)}/issue-token`, {
    method: "POST",
    credentials: "include",
  });
  if (!res.ok) throw new Error(`issueAgentToken ${res.status}`);
  return res.json();
}

export async function deleteAgent(name: string): Promise<void> {
  const res = await fetch(`${apiBase()}/api/agents/${encodeURIComponent(name)}`, {
    method: "DELETE",
    credentials: "include",
  });
  if (!res.ok) throw new Error(`deleteAgent ${res.status}`);
}
```

- [ ] **Step 3: TokenDisplay component**

`web/components/agents/token-display.tsx`:

```tsx
"use client";

import { useState } from "react";

export function TokenDisplay({ token }: { token: string }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    await navigator.clipboard.writeText(token);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }
  return (
    <div className="rounded-md border border-peach-neon/40 bg-peach-neon/5 p-3">
      <div className="mb-2 text-xs font-semibold text-peach-neon">
        Save this token — you won't see it again
      </div>
      <div className="flex items-center gap-2">
        <code className="flex-1 break-all rounded bg-carbon px-2 py-1 font-mono text-xs text-warm-fog">
          {token}
        </code>
        <button
          type="button"
          onClick={copy}
          className="rounded bg-aether-teal px-2 py-1 text-xs font-semibold text-carbon"
        >
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: NewAgentModal component**

`web/components/agents/new-agent-modal.tsx`:

```tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createAgent } from "@/lib/agents";
import { TokenDisplay } from "./token-display";

export function NewAgentModal({ onClose }: { onClose: () => void }) {
  const router = useRouter();
  const [name, setName] = useState("");
  const [language, setLanguage] = useState("python");
  const [description, setDescription] = useState("");
  const [githubUrl, setGithubUrl] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [issuedToken, setIssuedToken] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setPending(true);
    setError(null);
    try {
      const res = await createAgent({
        name,
        language,
        description: description || undefined,
        github_url: githubUrl || undefined,
      });
      setIssuedToken(res.token);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "unknown error");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={onClose}>
      <div
        className="w-full max-w-md rounded-2xl bg-warm-fog/5 p-6 shadow-xl ring-1 ring-aether-teal/20"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="mb-4 text-lg font-semibold text-aether-teal">
          {issuedToken ? "Agent created" : "Register new agent"}
        </h2>
        {issuedToken ? (
          <div className="space-y-3">
            <TokenDisplay token={issuedToken} />
            <p className="text-xs text-warm-fog/60">
              Set <code>LANGPERF_API_TOKEN</code> in your SDK environment.
            </p>
            <button
              type="button"
              onClick={onClose}
              className="w-full rounded bg-aether-teal px-3 py-2 text-sm font-semibold text-carbon"
            >
              Done
            </button>
          </div>
        ) : (
          <form className="space-y-3" onSubmit={onSubmit}>
            <label className="block text-xs text-warm-fog/70">
              Name (slug)
              <input
                required
                pattern="[a-zA-Z0-9][a-zA-Z0-9_-]*"
                className="mt-1 w-full rounded bg-carbon px-3 py-2 text-sm text-warm-fog"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </label>
            <label className="block text-xs text-warm-fog/70">
              Language
              <select
                className="mt-1 w-full rounded bg-carbon px-3 py-2 text-sm text-warm-fog"
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
              >
                <option value="python">Python</option>
                <option value="typescript">TypeScript</option>
                <option value="other">Other</option>
              </select>
            </label>
            <label className="block text-xs text-warm-fog/70">
              Description
              <input
                className="mt-1 w-full rounded bg-carbon px-3 py-2 text-sm text-warm-fog"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </label>
            <label className="block text-xs text-warm-fog/70">
              GitHub URL (optional)
              <input
                className="mt-1 w-full rounded bg-carbon px-3 py-2 text-sm text-warm-fog"
                value={githubUrl}
                onChange={(e) => setGithubUrl(e.target.value)}
              />
            </label>
            {error && <p className="text-xs text-warn">{error}</p>}
            <div className="flex gap-2">
              <button
                type="button"
                onClick={onClose}
                className="flex-1 rounded bg-carbon px-3 py-2 text-sm text-warm-fog/70"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={pending}
                className="flex-1 rounded bg-aether-teal px-3 py-2 text-sm font-semibold text-carbon disabled:opacity-50"
              >
                {pending ? "Creating..." : "Create"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 5: RowActions component**

`web/components/agents/row-actions.tsx`:

```tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { deleteAgent, issueAgentToken, rotateAgentToken } from "@/lib/agents";
import { TokenDisplay } from "./token-display";

export function RowActions({ name, hasToken }: { name: string; hasToken: boolean }) {
  const router = useRouter();
  const [issued, setIssued] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onIssue() {
    setPending(true);
    try {
      const r = await issueAgentToken(name);
      setIssued(r.token);
      router.refresh();
    } finally {
      setPending(false);
    }
  }
  async function onRotate() {
    if (!confirm(`Rotate token for ${name}? The old token stops working immediately.`)) return;
    setPending(true);
    try {
      const r = await rotateAgentToken(name);
      setIssued(r.token);
      router.refresh();
    } finally {
      setPending(false);
    }
  }
  async function onDelete() {
    if (!confirm(`Delete ${name}? This removes the agent and all its trajectories.`)) return;
    setPending(true);
    try {
      await deleteAgent(name);
      router.refresh();
    } finally {
      setPending(false);
    }
  }

  return (
    <>
      <div className="flex items-center gap-2">
        {!hasToken ? (
          <button
            type="button"
            onClick={onIssue}
            disabled={pending}
            className="rounded bg-peach-neon/20 px-2 py-1 text-[11px] text-peach-neon"
          >
            Issue token
          </button>
        ) : (
          <button
            type="button"
            onClick={onRotate}
            disabled={pending}
            className="rounded bg-carbon px-2 py-1 text-[11px] text-warm-fog/70 hover:text-warm-fog"
          >
            Rotate
          </button>
        )}
        <button
          type="button"
          onClick={onDelete}
          disabled={pending}
          className="rounded px-2 py-1 text-[11px] text-warn hover:bg-warn/10"
        >
          Delete
        </button>
      </div>
      {issued && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={() => setIssued(null)}>
          <div className="w-full max-w-md rounded-2xl bg-warm-fog/5 p-6 ring-1 ring-aether-teal/20" onClick={(e) => e.stopPropagation()}>
            <h3 className="mb-4 text-lg font-semibold text-aether-teal">New token</h3>
            <TokenDisplay token={issued} />
            <button
              type="button"
              onClick={() => setIssued(null)}
              className="mt-3 w-full rounded bg-aether-teal px-3 py-2 text-sm font-semibold text-carbon"
            >
              Done
            </button>
          </div>
        </div>
      )}
    </>
  );
}
```

- [ ] **Step 6: AgentsTable component**

`web/components/agents/agents-table.tsx`:

```tsx
"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { NewAgentModal } from "./new-agent-modal";
import { RowActions } from "./row-actions";
import type { AgentSummary } from "@/lib/api";

type Col = "name" | "language" | "token" | "last_used" | "created";

export function AgentsTable({ agents }: { agents: AgentSummary[] }) {
  const [filter, setFilter] = useState("");
  const [sort, setSort] = useState<{ col: Col; dir: "asc" | "desc" }>({ col: "name", dir: "asc" });
  const [showModal, setShowModal] = useState(false);

  const visible = useMemo(() => {
    const q = filter.trim().toLowerCase();
    const arr = agents.filter((a) =>
      !q ||
      a.name.toLowerCase().includes(q) ||
      (a.description ?? "").toLowerCase().includes(q) ||
      (a.language ?? "").toLowerCase().includes(q),
    );
    const cmp = (x: AgentSummary, y: AgentSummary): number => {
      switch (sort.col) {
        case "name": return x.name.localeCompare(y.name);
        case "language": return (x.language ?? "").localeCompare(y.language ?? "");
        case "token": return Number(Boolean(x.token_prefix)) - Number(Boolean(y.token_prefix));
        case "last_used":
          return new Date(x.last_token_used_at ?? 0).getTime() -
                 new Date(y.last_token_used_at ?? 0).getTime();
        case "created":
          return new Date(x.created_at).getTime() - new Date(y.created_at).getTime();
      }
    };
    arr.sort((a, b) => (sort.dir === "asc" ? cmp(a, b) : -cmp(a, b)));
    return arr;
  }, [agents, filter, sort]);

  function toggleSort(col: Col) {
    setSort((s) => (s.col === col ? { col, dir: s.dir === "asc" ? "desc" : "asc" } : { col, dir: "asc" }));
  }

  return (
    <>
      <div className="mb-3 flex items-center gap-2">
        <input
          placeholder="Filter agents..."
          className="flex-1 rounded bg-carbon px-3 py-2 text-sm text-warm-fog"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
        <button
          type="button"
          onClick={() => setShowModal(true)}
          className="rounded bg-aether-teal px-3 py-2 text-sm font-semibold text-carbon"
        >
          + Add agent
        </button>
      </div>

      <div className="overflow-hidden rounded border border-[color:var(--border)] bg-[color:var(--surface)]">
        <table className="w-full text-left text-xs">
          <thead className="bg-carbon text-[10px] uppercase text-warm-fog/60">
            <tr>
              <Th label="Name" onClick={() => toggleSort("name")} active={sort.col === "name"} dir={sort.dir} />
              <Th label="Lang" onClick={() => toggleSort("language")} active={sort.col === "language"} dir={sort.dir} />
              <Th label="Token" onClick={() => toggleSort("token")} active={sort.col === "token"} dir={sort.dir} />
              <Th label="Last used" onClick={() => toggleSort("last_used")} active={sort.col === "last_used"} dir={sort.dir} />
              <Th label="Created" onClick={() => toggleSort("created")} active={sort.col === "created"} dir={sort.dir} />
              <th className="px-3 py-2 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {visible.length === 0 ? (
              <tr><td colSpan={6} className="p-6 text-center text-warm-fog/50">No agents yet. Click "+ Add agent" to register one.</td></tr>
            ) : visible.map((a) => (
              <tr key={a.id} className="border-t border-[color:var(--border)]">
                <td className="px-3 py-2">
                  <Link href={`/agents/${a.name}/overview`} className="text-aether-teal hover:underline">
                    {a.name}
                  </Link>
                  {a.description && <div className="text-[10px] text-warm-fog/50">{a.description}</div>}
                </td>
                <td className="px-3 py-2 text-warm-fog/70">{a.language ?? "—"}</td>
                <td className="px-3 py-2">
                  {a.token_prefix ? (
                    <code className="rounded bg-carbon px-1.5 py-0.5 font-mono text-[10px] text-warm-fog/80">
                      {a.token_prefix}…
                    </code>
                  ) : (
                    <span className="rounded bg-peach-neon/20 px-1.5 py-0.5 text-[10px] text-peach-neon">unregistered</span>
                  )}
                </td>
                <td className="px-3 py-2 text-warm-fog/70">
                  {a.last_token_used_at ? new Date(a.last_token_used_at).toLocaleString() : "—"}
                </td>
                <td className="px-3 py-2 text-warm-fog/70">{new Date(a.created_at).toLocaleDateString()}</td>
                <td className="px-3 py-2 text-right">
                  <RowActions name={a.name} hasToken={Boolean(a.token_prefix)} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showModal && <NewAgentModal onClose={() => setShowModal(false)} />}
    </>
  );
}

function Th({ label, onClick, active, dir }: { label: string; onClick: () => void; active: boolean; dir: "asc" | "desc" }) {
  return (
    <th
      onClick={onClick}
      className="cursor-pointer select-none px-3 py-2 hover:text-warm-fog"
    >
      {label}{active && (dir === "asc" ? " ▲" : " ▼")}
    </th>
  );
}
```

- [ ] **Step 7: Rewrite `web/app/agents/page.tsx`**

```tsx
import { AppShell } from "@/components/shell/app-shell";
import { AgentsTable } from "@/components/agents/agents-table";
import { Chip } from "@/components/ui/chip";
import { listAgents } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function AgentsPage() {
  const agents = await listAgents();
  return (
    <AppShell
      topBar={{
        breadcrumb: <span className="font-medium text-warm-fog">Agents</span>,
        right: <Chip>{agents.length} agent{agents.length === 1 ? "" : "s"}</Chip>,
      }}
    >
      <AgentsTable agents={agents} />
    </AppShell>
  );
}
```

- [ ] **Step 8: Commit**

```
git add web/app/agents/page.tsx web/components/agents/ web/lib/agents.ts web/lib/api.ts
git commit -m "feat(agents): sortable table + register/rotate/delete UI"
```

---

## Task 6 — Python SDK: Bearer token header

**Files:**
- Modify: `sdk/langperf/tracer.py`
- Modify: `sdk/README.md`

**Steps:**

- [ ] **Step 1: Add token to OTLP exporter**

In `sdk/langperf/tracer.py`, locate the `init()` function where `OTLPSpanExporter(endpoint=...)` is constructed. Replace with:

```python
token = api_token or os.environ.get("LANGPERF_API_TOKEN")
if not token:
    raise RuntimeError(
        "LANGPERF_API_TOKEN is required. Register an agent in the UI and set "
        "the token via LANGPERF_API_TOKEN or the api_token kwarg."
    )
exporter = OTLPSpanExporter(
    endpoint=f"{endpoint}/v1/traces",
    headers={"Authorization": f"Bearer {token}"},
)
```

Extend `init(..., api_token: str | None = None)` signature accordingly.

- [ ] **Step 2: Update `sdk/README.md`**

Add a "Setup" section near the top:

```markdown
### Setup

1. Register your agent in the LangPerf UI (Agents → + Add agent). You'll
   receive an API token — save it; it's shown once.
2. Set the token in your environment:

   ```bash
   export LANGPERF_API_TOKEN=lp_xxxxxxxx_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```

3. Initialize:

   ```python
   import langperf
   langperf.init()  # reads LANGPERF_API_TOKEN from env
   # or
   langperf.init(api_token="lp_...")
   ```
```

- [ ] **Step 3: Commit**

```
git add sdk/langperf/tracer.py sdk/README.md
git commit -m "feat(sdk): send LANGPERF_API_TOKEN as Bearer on OTLP export"
```

---

## Task 7 — Remove sdk-keys settings placeholder

**Files:**
- Modify: `web/components/shell/nav-config.ts`
- Modify: `web/app/settings/[section]/page.tsx` (if it references sdk-keys)

**Steps:**

- [ ] **Step 1: Drop `sdk-keys` from `SETTINGS_SECTIONS`**

In `web/components/shell/nav-config.ts`, remove:

```ts
{ id: "sdk-keys",       label: "SDK keys",            href: "/settings/sdk-keys",        group: "integrations" },
```

- [ ] **Step 2: Handle route**

If `web/app/settings/[section]/page.tsx` renders a branch for `section === "sdk-keys"`, replace with a redirect to `/agents` (via `import { redirect } from "next/navigation"`).

- [ ] **Step 3: Commit**

```
git add web/components/shell/nav-config.ts web/app/settings/
git commit -m "chore(settings): retire sdk-keys placeholder — replaced by per-agent tokens"
```

---

## Task 8 — End-to-end smoke

**Manual steps — run against the live docker compose stack:**

- [ ] Navigate to `/agents` → click "+ Add agent" → fill name/language → submit.
- [ ] Verify the token modal appears once; copy it.
- [ ] Set `export LANGPERF_API_TOKEN=<copied>` in a shell.
- [ ] Run a short SDK script that exports a trace.
- [ ] Verify a new trajectory appears under that agent within a second.
- [ ] On the agent row, click "Rotate"; copy new token; confirm old token now returns 401 on ingest.
- [ ] Click "Delete" on a throwaway agent; confirm the row disappears and historical runs are gone.
- [ ] On a pre-existing (legacy) agent row, click "Issue token"; verify ingest works with the new token.

Close the loop by committing any doc fixes that surface during smoke.

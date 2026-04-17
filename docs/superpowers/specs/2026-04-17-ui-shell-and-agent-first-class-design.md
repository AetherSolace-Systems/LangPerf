# UI Shell, Dashboard, and First-Class Agent — Design

Date: 2026-04-17
Status: Spec · awaiting review
Scope: v1 dogfood — adds the information architecture and data-model foundation that everything else in the vision (triage, evals, training-data export, collaboration) will hang off of.

---

## 1. Motivation

The current web app has two routes — a trajectory list and a trajectory detail. That's enough to prove the ingest pipeline works, but it isn't an application. Before adding any more deep features (triage, evals, clusters), we need a proper navigation shell and a mental model the rest of the product can fit into.

The organizing unit is the **Agent**. Until now we've had `service.name` on trajectories and nothing else; the product treats every run as a flat row. That pushes all the "which of my agents is getting worse?" questions into manual filtering. An Agent needs to be a first-class thing with identity, versions, environments, and history — because the whole vision (process optimization: improve prompts, tool definitions, agent harness structure) is about one agent evolving over time.

This spec covers:

1. A new IA / navigation shell (Dashboard / Agents / History / Logs / Settings, with v2 sections visible but disabled).
2. First-class Agent + Run data model, with auto-detected Agent identity (no user registration step).
3. Screen-level design for the five sections above, including charts, filters, and placeholders for v2 features.
4. A new "Aether Dusk" palette replacing the current Drift Signal palette for a more serious, industrial look.

Out of scope (explicit v2 deferrals): triage queue, eval sets, training-data export, comments/reviewers, replay-against-new-prompt, users/orgs/billing/SSO.

---

## 2. Vocabulary

| Term | Definition |
|---|---|
| **Agent** | A first-class entity representing one harness/process captured via the SDK. Auto-detected from the source. Has name, description, owner, github link, versions, environments, runs. |
| **Run** | A single end-to-end execution of an agent. Replaces "trajectory" as the user-facing noun, though `trajectory` remains the internal/legacy synonym during transition. |
| **Step** | A single action inside a run — LLM call, tool call, thinking block. (Unchanged — already called "node" / "step" in existing code.) |
| **Version** | A specific revision of an agent's code. Captured as git SHA + package-version where available. |
| **Environment** | Deployment environment (dev / staging / prod). Sourced from OTel `deployment.environment`. |
| **Signature** | A stable fingerprint of agent identity used to auto-create the Agent row on first sight. See §4. |

All existing instances of "trajectory" in the UI will be renamed to "run". The OTLP wire format and database column names stay (rename cost isn't worth it; these are internal).

---

## 3. Palette — Aether Dusk

Replaces the current "Drift Signal" palette in `web/app/globals.css` and `web/tailwind.config.ts`.

| Role | Name | Hex | Usage |
|---|---|---|---|
| Background | Carbon | `#181D21` | Page backgrounds |
| Surface | Steel Mist | `#242D32` | Cards, panels |
| Surface-2 | — | `#1F272B` | Secondary surfaces (rail, identity strip) |
| Primary | Aether Teal | `#6BBAB1` | Primary actions, brand, "ok" data |
| Secondary | Peach Neon | `#E8A87C` | Warm accents, "noted" tags, secondary data |
| Warn | — | `#D98A6A` | Errors, "bad" tags (slightly deeper peach) |
| Text | Warm Fog | `#F2EAE2` | Primary text |
| Muted | Patina | `#7A8B8E` | Metadata, labels |
| Border | — | `#2E3A40` | 1px hairlines |
| Border-strong | — | `#3A4950` | Chip outlines, seg-picker dividers |

**Typography:** Inter for reading text, JetBrains Mono for numbers, labels, IDs, and all uppercase metadata. Body 13px, KPI 20px mono 500-weight, label 9–10px uppercase 1.2px letter-spacing.

**Density & feel:** 3px card corners, 2px pill corners, 1px hairlines with occasional 2px accent-colored left-borders for v2 teasers. No filled color pills except primary-action chips. Charts use 1.2–1.5px lines with faint dashed gridlines (no heavy grids). The result should read more industrial (Bloomberg / Linear / Vercel monitoring) than playful.

---

## 4. Data model — First-class Agent

### 4.1 New tables

```
agents
  id                uuid pk
  signature         text unique       -- fingerprint, see §4.2
  name              text              -- auto-generated docker-style (e.g. "crimson-dagger"), user-renamable
  display_name      text nullable     -- optional human name override
  description       text nullable
  owner             text nullable
  github_url        text nullable
  language          text              -- auto-detected ("python", "typescript", ...)
  created_at        timestamp
  updated_at        timestamp

agent_versions
  id                uuid pk
  agent_id          uuid fk -> agents.id
  git_sha           text nullable     -- when available
  short_sha         text nullable     -- first 7 chars
  package_version   text nullable     -- when available
  label             text              -- resolved: package_version OR "sha:<short>"
  first_seen_at     timestamp
  last_seen_at      timestamp
  unique(agent_id, git_sha, package_version)
```

### 4.2 Agent signature

Stable across runs of the same agent code, different across different codebases. Composed at SDK `init()` time:

1. If `git remote get-url origin` returns a value: `git:<origin>:<path-to-init-caller-relative-to-repo-root>`
2. Otherwise: `mod:<hostname>:<module-path-of-init-caller>`

Captured in Python via `inspect.stack()` at `langperf.init()`.

Hash as SHA-256, take first 16 hex chars → that's the stored `signature`.

First time an unknown signature arrives, the backend:
- Creates `agents` row with auto-generated docker-style `name` (adjective + noun, e.g. `crimson-dagger`).
- Infers `language` from the SDK user-agent header.
- If git-derived, infers `github_url` (when origin is a github URL) and sets `description` to the repo path.
- Marks it as needing admin review (surfaced on Settings → Agents).

### 4.3 Changes to existing `trajectories` table

Add three nullable columns (backward compatible):

```
trajectories
  agent_id          uuid fk -> agents.id      -- populated on ingest
  agent_version_id  uuid fk -> agent_versions.id
  -- service_name (existing) stays as-is; `agent_id` supersedes it for new data
```

Backfill: for existing rows with no signature, create one synthetic Agent per distinct (service_name, environment) pair and point the rows at it. That preserves historical data without forcing users to re-ingest.

### 4.4 SDK changes

`langperf.init()` (Python):
- Detects signature at startup (git + inspect.stack).
- Reads `package_version` from `importlib.metadata` when the caller's module belongs to an installed package.
- Sends both as OTel resource attributes: `langperf.agent.signature`, `langperf.agent.version.sha`, `langperf.agent.version.package`.

No explicit `register()` call. Zero-config.

### 4.5 URL scheme

- `/` — dashboard
- `/agents` — agents index
- `/agents/<name>` — agent detail (default tab: overview)
- `/agents/<name>/<tab>` — runs / prompt / tools / versions / config
- `/agents/<name>/runs/<run_id>` — run detail (existing trajectory detail, rehomed)
- `/history` — run history (global)
- `/logs` — server logs
- `/settings` — settings (defaults to Log forwarding)
- `/settings/<section>` — deep links into settings sections
- `/r/<run_id>` — short permalink that redirects to the above (for export/share)

Legacy `/t/<id>` redirects to `/r/<id>`.

---

## 5. Navigation shell

Three-zone layout applied globally:

1. **Top bar** (48px): logo, breadcrumb, global search (⌘K), env pill, environment-wide KPIs that make sense per-page (e.g. "ingest ok" on dashboard, last-run timer on agent detail).
2. **Icon rail** (56px wide): labeled stack of sections (HOME / AGENTS / HISTORY / LOGS, a divider, v2 placeholders TRIAGE / EVALS / DATA at reduced opacity, then CONFIG at the bottom). Active state is a 2px teal left-border plus a 4% teal tint on the rail cell. V2 items have `tabindex="-1"` and show a "v2" tooltip on hover; they are visibly disabled, not clickable.
3. **Context sidebar** (220px wide): content changes per section. On Agents: list of agents. On an agent: versions + environments + saved filters. On History: saved patterns + quick filters. On Logs: sources + levels + forwarding status. On Settings: section nav.

On agent and run pages, an **Identity strip** lives directly below the top bar: Agent / Version / Env chips + live numbers (last-run time, /day, p50/p95, error rate). This is the page's anchor for "which agent am I looking at, in what version, in what environment?"

---

## 6. Screens

### 6.1 Dashboard (`/`)

Goal: big-picture view across all monitored agents. Time-range picker top-right (24h / 7d / 30d) scopes everything below.

Layout (top to bottom):

- **KPI strip** (5 tiles): runs in range, agents (with dev/stg/prod breakdown), error rate, p95 latency, flagged count. Each tile shows w/w delta.
- **Run volume × time** stacked by environment (prod/staging/dev), vertical bar chart with x-axis day labels.
- **Error rate × time** line chart with a peak annotation.
- **Top tools across all agents** horizontal bar list.
- **Latency p50/p95 trend** line chart.
- **Environment split** horizontal bar with counts.
- **Agent grid** — one card per monitored agent, 4-up, with name / version / per-day total / error rate / p95 / mini line chart sparkline.
- **Recent flagged table** (4–5 rows, columns: id / agent + summary / tag / time).
- **Tool-by-agent heatmap** — rows = agents, columns = tool names, cell intensity = call count. Surfaces optimization insights like "docs-qa never calls http, should it?".
- **V2 teaser row** (3 cards): Triage queue, Eval regressions, Training data export.

### 6.2 Agents index (`/agents`)

Header with "new agents detected" callout when auto-signatures are unclaimed. Grid of agent cards (same shape as dashboard's agent grid but full-size). Click-through to agent detail.

### 6.3 Agent detail (`/agents/<name>`)

Identity strip at the top. Sub-nav tabs: **Overview** (default) · Runs · Prompt · Tools · Versions · Config.

**Overview tab** layout:

- **KPI strip** (5 tiles, agent-scoped): runs 7d, error rate, p95 latency, tools called, flagged count.
- **Row 1** (2 columns):
  - Run volume last 7d, stacked by version, x-axis = day labels. So a new rollout is visible as a stripe climbing the stack.
  - Latency chart last 24h with **p50 / p95 / p99** lines, explicit Y-axis (0 / 3s / 6s / 9s / 12s), X-axis (−24h / −18h / −12h / −6h / now), 10-min buckets.
- **Row 2** (2 columns):
  - Tokens & cost last 24h — dual-axis: stacked token bars (input dark, output light) on left; cost line on right. Subtotal footer.
  - Top tools for this agent with per-tool error rates, and an inline callout when any tool's error rate is rising.
- **Row 3** (full width): Recent runs table with columns: Time (full datetime) · ID · Input · Steps · Tools · Tokens (in/out) · Cost · Latency · Status tag. Auto-refresh chip next to the header. Columns match the global History table for consistency.
- **V2 teasers** (3 cards): Eval set pass rate · Comments & reviewers · Replay against new prompt.

No sequence-graph hero, no version-history details on this tab (both live on other tabs).

**Other tabs (structure only — content to be spec'd in follow-up):**

- **Runs tab** — full run list scoped to this agent, same columns as History but with agent column suppressed.
- **Prompt tab** — view current system prompt, diff across versions, rendered variable slots.
- **Tools tab** — tool defs registered by this agent, per-tool usage stats, argument distributions.
- **Versions tab** — version timeline with change summary (prompt ±lines, tools added/removed), promotion history across envs.
- **Config tab** — rename agent, edit description/owner/github, environment mapping, archive.

### 6.4 Run detail (`/agents/<name>/runs/<run_id>`)

Existing trajectory detail page, rehomed under the agent. Already good — sequence graph + step tree + kind-aware right panel — so this spec does not redesign it, just adds the identity strip and breadcrumb.

### 6.5 History (`/history`)

Global run search, chronological descending, auto-refresh.

- **Pattern input** (hero): `agent.env.version` fuzzy syntax with `*` wildcards. Examples:
  - `support-*.prod.*` → all runs of any `support-*` agent in prod, any version
  - `triage-router.*.v2.*` → triage-router across all envs on v2.x
  - `*.test.*` → all agents in test env
  - `v1.4.*` version globs work with semver-aware matching
- **Controls**: auto-refresh toggle (5s default), time-range chip, status filter, tag filter.
- **Saved patterns sidebar** + quick filters (flagged · 24h, latency > 10s, errors only, new agents).
- **Table**: Time / Agent / Ver / Env / ID / Input / Steps / Tokens / Cost / Latency / Status. Same columns as agent-detail Recent runs, plus the agent/ver/env columns that are implicit there.
- **Export**: CSV and JSONL of the current filtered view.
- Pagination: offset-based is fine for dogfood (cursor-based is in the v2 roadmap).

### 6.6 Logs (`/logs`)

Real-time server-side log stream. Separate from run data.

- **Pattern input**: `source:api-server level:>=info` style filters, free-text search.
- **Controls**: follow/tail toggle (default on), pause, clear, wrap.
- **Sidebar**: source list (api-server / ingest / otel-collector / web / postgres) with live throughput, level toggles (INFO / WARN / ERROR / DEBUG), forwarding status snapshot with a link to Settings.
- **Console**: JetBrains Mono, color-coded levels, structured KV highlighting, 10k-line buffer with scrollback.
- **Export**: last hour as JSONL.

No user logs here — those live inside runs. This page is for "is my LangPerf backend healthy?"

### 6.7 Settings (`/settings`)

Left section nav: Workspace · Observability · Integrations · Later (v2 group). Default route is Log forwarding.

**Log forwarding** — the main v1 observability surface:

- **Datadog**: toggle, site, env-var-bound API key, live events-forwarded counter.
- **Grafana Loki**: toggle, endpoint, labels, counter.
- **Generic OTLP**: toggle, endpoint, headers (honeycomb, tempo, signoz, jaeger all use this).
- **Local file**: toggle, path, rotation policy.
- **What gets forwarded** (card with 4 toggles): server logs · agent trace events · full trajectory payloads (noisy — off by default) · SDK-client diagnostic logs.

**Workspace**:

- **Profile** — single-user placeholder in v1, becomes real on multi-user.
- **Environments** — name them, order them, rename (dev / staging / prod are defaults from `deployment.environment`).
- **Agents · auto-detected** — the queue of signatures pending human review. Rename, describe, set owner, link github, or archive.

**Integrations** — SDK keys + Webhooks (basic).

**Later (v2 placeholder group)** — Users & org · Billing · SSO / SAML. Visible but disabled.

---

## 7. V2 placeholder treatment

Consistent across the product:

- **Rail items**: reduced opacity (0.55), dashed border around the glyph, no hover state, no click target. Tooltip reads "v2 · coming soon".
- **Cards**: 2px peach (secondary) left-border, tiny uppercase "v2" badge in peach, title + one-line description. No "join waitlist" CTAs — this is a dogfood build; the user IS the waitlist.
- **Dashboard & agent-detail teasers** sit at the bottom of their pages, three-up.

The aim is to signal future direction without faking interactivity. No dead links.

---

## 8. What this replaces / impacts

### 8.1 Web app changes

- `web/app/layout.tsx` gains the nav shell (rail + top bar).
- `web/app/globals.css` + `web/tailwind.config.ts` swap to Aether Dusk palette.
- `web/app/page.tsx` (currently trajectory list) becomes the dashboard.
- New routes: `/agents`, `/agents/[name]`, `/agents/[name]/[tab]`, `/history`, `/logs`, `/settings`, `/settings/[section]`, `/r/[run_id]`.
- Existing `/t/[id]` becomes a redirect.
- New API endpoints (see §8.2).
- Recent-runs table component is reused in three places (dashboard / agent-detail overview / history) with column visibility flags.

### 8.2 API additions

- `GET /api/agents` — list with per-agent summary metrics.
- `GET /api/agents/{name}` — detail with versions, environments, KPIs.
- `GET /api/agents/{name}/metrics?window=24h|7d|30d&by=version|env` — run volume, latency percentiles, tokens, cost aggregates.
- `GET /api/agents/{name}/tools?window=...` — per-tool call counts and error rates.
- `GET /api/agents/{name}/runs?...` — scoped run list.
- `PATCH /api/agents/{name}` — rename, update description/owner/github.
- `GET /api/runs?pattern=...&limit=...&offset=...&refresh=true` — global run search with pattern parser.
- `GET /api/logs/stream` — SSE stream for the Logs page (one event per log line).
- `GET /api/settings/forwarding`, `PATCH /api/settings/forwarding/{target}` — log forwarding config.

Pattern parser (history page): split on `.` into exactly three segments (`agent.env.version`). Each segment becomes a glob against the corresponding field (agent_name / environment / version_label). `*` matches a whole segment; `foo-*` / `*-bot` / `*foo*` match parts. Version-label matching is a pure string glob — `v1.4.*` matches `v1.4.0`, `v1.4.2`, but also `v1.4.x-rc.1` (that's fine for v1, semver-aware matching can come later). Missing trailing segments default to `*`.

### 8.3 SDK additions

- Capture `agent.signature` at `init()` time via stack inspection + git probe.
- Capture `agent.version.sha` (short + full) and `agent.version.package` when available.
- Attach all three as OTel resource attributes with `langperf.` prefix.
- These are added on top of existing attributes; no behavior change for existing users beyond new metadata appearing on their runs.

### 8.4 Ingest / backend additions

- On first sight of an unknown signature: create Agent row with auto-generated name, infer language + github_url.
- On every run: upsert `agent_versions` row keyed on (agent_id, git_sha, package_version), populate `trajectories.agent_id` and `agent_version_id`.
- Backfill migration: one synthetic Agent per distinct `service_name` (environments stay a property of runs, not agents), with a `legacy:` signature prefix so they're visibly "unreviewed" in settings.
- Log forwarding sinks: implement Datadog, Grafana Loki, OTLP, local file as pluggable back-end writers fed off a single event bus inside the Python API service.

---

## 9. Success criteria

1. Landing on `/` shows the dashboard with real data from existing LM Studio dogfood runs — no 404s, no placeholder-only tiles.
2. Every run ingested by the SDK is assigned to an Agent automatically. Running the same code from two different git repos creates two distinct Agents. Running the same code with different package versions creates one Agent, two versions.
3. The fuzzy pattern `support-*.prod.*` on `/history` returns exactly the expected set.
4. Enabling Grafana Loki forwarding in Settings and triggering runs causes events to appear in Loki within 5 seconds.
5. Auto-detected agents show up on Settings → Agents with docker-style names; renaming them propagates everywhere the name is displayed.
6. The Aether Dusk palette is applied site-wide — no leftover purple/marigold from Drift Signal.
7. All v2 placeholder sections/cards are visible but non-interactive; no dead clicks.

---

## 10. Explicit non-goals in this spec

- The Prompt / Tools / Versions / Config tabs on agent detail are structurally declared but their content is out of scope for this spec. Follow-up specs will detail each.
- The Runs tab on agent detail is structure-only; it's essentially `/history` pre-filtered to one agent and its own spec would be trivial.
- No triage queue, no clusters, no eval integration, no comments, no users. These are v2 per `docs/ROADMAP.md`.
- No refactor of the run-detail page itself — it gets the new shell and identity strip but its internals (graph / tree / right panel) stay as-is.

---

## 11. Suggested implementation phasing

This spec describes a target state. The implementation plan should split it into sequenced phases so each can ship and be dogfooded independently. A reasonable cut:

1. **Foundations** — Aether Dusk palette + nav shell + rail/context-sidebar component + route scaffolding for all sections (with placeholder content). No data changes. The shell is the product's new bones.
2. **First-class Agent** — agents + agent_versions tables, signature capture in SDK, ingest-side upsert, backfill migration. Agents index and agent-detail Overview (using new data). This is the biggest phase because UI, SDK, and ingest all move together.
3. **Dashboard** — compose the big-picture screen using aggregations over the new Agent data.
4. **History** — pattern parser + global run search + auto-refresh.
5. **Logs + Settings · Log forwarding** — SSE stream, sinks (Datadog / Loki / OTLP / file), Settings UI.
6. **V2 placeholders + polish** — all the disabled teasers, copy review, empty states, permalink redirects.

Phases 1–2 must ship together (the shell without Agents is confusing; the data without UI is invisible). 3–6 can ship independently in any order.

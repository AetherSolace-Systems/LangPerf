# Roadmap

v1 is deliberately tight. This document tracks everything from the full vision
(`docs/vision.md`) that's **explicitly not shipping in v1**, organized by theme
so we can pull items up into a specific future version as the product evolves.

## v1 (shipping)

- Local `docker compose` deployment (FastAPI + Next.js + Postgres)
- OTLP/HTTP ingestion at `/v1/traces` (JSON + protobuf)
- Python `langperf` SDK: `init`, `trajectory`, `node`, `flush`
- Trajectory list + detail with collapsible tree viewer
- Graph view (React Flow + dagre auto-layout) with pan / zoom / minimap — selection synced with the tree
- Kind-aware right panel (LLM / tool / generic)
- Manual tagging (`good` / `bad` / `interesting` / `todo`) + free-form notes on trajectories and nodes
- Filter by tag / service / environment, free-text search across span content
- Environment separation via OTel `deployment.environment`
- Verbose content capture by default
- Graceful handling of LM Studio (cost=null tolerated; `base_url` agnostic)

---

## Deferred to v2+

### Collaboration (the differentiator — this is what v2 is "about")
- Comments/threads on any node
- @-mentions, notifications
- Assign trajectories to a reviewer
- Auth, multi-user, organizations, projects
- SME reviewer role with lightweight seat pricing
- Shared trajectory links (read-only, auth-gated)

### Annotation → training data
- Branched rewrites ("here's what the agent should have done from step N onward")
- Automatic preference-pair generation
- Failure-mode taxonomy (wrong tool, bad args, hallucination, loop, etc.)
- JSONL export for SFT / DPO / step-level reward
- Direct integrations with Together, Fireworks, OpenAI fine-tuning, HF TRL
- CSV export of tagged failures for analytics / roadmap

### Triage & intelligence
- Automated heuristics: latency spikes, tool errors, loop detection, apology-phrase detection, low-confidence outputs
- Cluster detection ("47 runs failed the same way this week")
- Anomaly detection on trajectory shapes
- Priority-ordered triage queue as the default landing page
- Inter-annotator agreement + rubrics

### Developer loop
- Side-by-side diff of two trajectories
- Graph viewer upgrades (perf tuning for 1k+ node trajectories, node grouping, custom layouts, branch collapse in graph — tree already supports collapse)
- Replay-against-new-prompt in dev ("would v2 have gotten this right?")
- Eval sets derived from flagged clusters
- Regression CI (run flagged clusters against every prompt change)
- Integration with Promptfoo / Braintrust

### Ecosystem reach
- TypeScript / JavaScript SDK
- Framework integrations beyond raw OpenAI SDK:
  - Claude Agent SDK
  - OpenAI Agents SDK
  - LangChain / LangGraph
  - LlamaIndex / LlamaIndex Workflows
  - CrewAI
  - Vercel AI SDK (TypeScript)
- `gen_ai.*` OTel semconv parity (we already accept it; more UI affordances for it)

### Export surface
- Trace permalinks → Slack / Linear / GitHub issues
- Markdown pattern summaries → Notion / Confluence
- Failure-mode charts, dashboards, reports

### Operations & scale
- Cloud / SaaS deployment
- SSO, audit logs, data residency
- Self-hosted with enterprise features (paid tier)
- ClickHouse or other columnar store for large trace volumes
- WebSocket / SSE for real-time UI updates (currently polling-free by way of server-component fetch-on-load)
- Sampling, rate limiting
- Kubernetes deployment docs
- Cursor-based pagination upgrade (currently offset-based — fine at dogfood scale)

### UX polish
- Mobile reviewer experience (small-screen layouts)
- Keyboard shortcuts for triage
- Saved views / custom filters
- Dark/light theme toggle (currently dark-only)
- Payload search upgrade (tsvector + GIN vs current ILIKE on JSONB text)

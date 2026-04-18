# LangPerf V2 — Development Roadmap

**Status:** Strategic scoping doc. Not a release plan — a development roadmap.
**Date:** 2026-04-17
**Scope:** Defines the v2 development phase (Collaboration + Triage), sequences what follows, and names the decision gates between them.

> This is the strategic companion to `docs/ROADMAP.md`. ROADMAP is the full backlog of what's "not in v1." This doc is opinionated about what to build next and in what order.

---

## V2 thesis & shape

**V2 in one line:** The first multi-human LangPerf — still OSS, still self-hosted, still no cloud, designed from the ground up for at least two people (an engineer and an SME) to work a real agent quality problem together.

**Who uses v2:**
- Andrew (continues dogfooding on his own agent work)
- Optionally 1–2 pilot teams, at Andrew's discretion, after v2 feels complete

**V2 is not:**
- **Not a release.** These are development milestones, not release milestones. V2 ships when Andrew is happy with it.
- **Not the hosted/cloud launch.** `langperf.com` does not go live as a SaaS in v2. No signups, no multi-tenant infra, no SSO.
- **Not the public OSS drop.** Public OSS launch is a later gate (see Gate 4), once the full improvement loop is built out.
- **Not a full-ecosystem release.** TS SDK and broad framework wrappers stay deferred.

**Quality posture:** No deadline, no budget. Build it right the first time rather than shipping a thin prototype. "Right the first time" means good data model, well-considered abstractions, full design surface — not "everything and the kitchen sink."

---

## Finishing v1

No formal hardening phase. V1 development continues until Andrew's own dogfood loop is productive and "I wish I had a second human in here" becomes the top unmet need. That's the signal to pivot to v2 work (see Gate 1).

---

## V2 scope — Collaboration + Triage

V2 is two buckets, both built to full quality. Everything else is out.

### Collaboration surface

- **Multi-user auth**, minimum viable. Email + password or magic link. No SSO, no external IdP. Degrades gracefully to single-user mode so Andrew-solo still works without login friction.
- **Orgs / workspaces:** one org per deployment. Deployment = org. Multi-org support waits for cloud.
- **Comments / threads on any node.** Markdown, edit, delete, resolve.
- **@-mentions + notifications.** In-app notification center minimum; email optional.
- **Reviewer assignment.** Assign a trajectory to a specific user; "assigned to me" filter on the triage queue.
- **Shared links.** Auth-gated by default. Optional "share read-only to anyone in the org" flag. No public shares in v2.
- **Failure-mode taxonomy UI.** Layered on top of v1's manual tags (`good` / `bad` / `interesting` / `todo`). Taxonomy: wrong tool, bad args, hallucination, loop, misunderstood intent. Drives triage clustering.
- **Branched-rewrite annotation UI.** SMEs can annotate "here's what the agent should have done from step N onward." The rewrite is stored as structured annotation data; the *export* side (preference-pair JSONL, fine-tuning integrations) is v3. In v2, the rewrite is a first-class SME annotation primitive but doesn't leave the tool.

### Triage queue

- **New default landing page** for logged-in users. Replaces the current dashboard as the default route; dashboard remains one click away.
- **Automated heuristics — full set, tuned against real data:**
  1. Tool-call errors
  2. Latency outliers (p95 per agent+tool)
  3. Apology-phrase detection on final outputs
  4. Loop detection (same node-kind + args repeating N times)
  5. Low-confidence / refusal detection
- **Cluster view.** Group trajectories with similar failure shape. Heuristic-based, not ML. Example: "47 runs triggered the `search_orders` error this week."
- **Queue-first UX.** Open LangPerf, see the top N prioritized things, work them. Filters by heuristic, tag, failure-mode, and assigned reviewer.

### Reconciliation with v1

- V1's manual tagging system stays untouched. Failure-mode taxonomy is additive.
- V1's live log streaming, agent detail tabs (Runs/Tools/Versions/Config/Prompt/Logs), dashboard, history — all stay untouched.
- V1's existing data capture is sufficient for all 5 heuristics.

### Explicitly NOT in v2

- Preference-pair / JSONL export (v3)
- Direct fine-tuning integrations (v3)
- Slack / Linear / GitHub trace permalinks (v3)
- Markdown summary export for Notion / Confluence (v3)
- Trajectory diff (v4)
- Replay-against-new-prompt (v4)
- Eval sets derived from clusters (v4)
- Regression CI, Promptfoo / Braintrust integration (v4)
- TS / JS SDK (v5)
- Framework wrappers beyond raw OpenAI SDK (v5, or opportunistic)
- Cloud / SSO / enterprise features (demand-gated, post-Gate 5)

---

## Post-v2 sequencing

Dependency order + strategic priority. No dates.

### V3 — Close the improvement loop

The output side. V2 captures, triages, and annotates. V3 is what gets the *result* of that work back into the team's actual tools.

- Preference-pair generation from v2's branched rewrites
- JSONL output for SFT / DPO / step-level reward
- Failure-mode CSV export for analytics
- Trace permalinks → Slack, Linear, GitHub issues
- Markdown pattern summaries → Notion, Confluence
- Direct integrations with Together, Fireworks, OpenAI fine-tuning, HF TRL (at least one to prove the loop)

**Rationale:** Without V3, LangPerf is a roach motel — data in, nothing out. V3 is the vision's "improvement loop" actually closing.

### V4 — Developer loop

For *engineers* consuming the SME signal that V2+V3 produce.

- Trajectory diff (side-by-side, same input / different prompt or model version)
- Replay-against-new-prompt ("would v2 have gotten this right?")
- Eval sets derived from flagged clusters
- Regression CI (run flagged clusters against every prompt change)
- Promptfoo / Braintrust integration

**Rationale:** Replay and diff amplify what V3's export already provides and strengthen the engineer-facing pitch. Only worth building after the SME side produces structured feedback worth replaying against.

### V5 — Ecosystem reach

Coverage for broader adoption, primarily in service of the OSS launch (Gate 4).

- TypeScript / JavaScript SDK
- Framework wrappers: Claude Agent SDK, OpenAI Agents SDK, LangChain / LangGraph, LlamaIndex / LlamaIndex Workflows, Vercel AI SDK (TypeScript), CrewAI
- Broader OTel GenAI semconv UI affordances (already accepted; needs more UI)

**Rationale:** Coverage matters for adoption, not for the core loop. Worth investing in when it's time to broaden past the initial Python-OpenAI shape.

**Note:** Individual framework integrations can be pulled forward opportunistically if one becomes important to Andrew's own work (e.g., if he starts using Claude Agent SDK himself, that wrapper jumps the queue).

### Demand-gated — post-Gate 5

Deferred until OSS launch produces a demand signal. Not indefinite — demand-gated.

- Cloud / SaaS hosting (`langperf.com` as a product)
- SSO, audit logs, data residency
- Enterprise self-hosted tier
- ClickHouse / columnar storage for large trace volumes
- WebSocket / SSE for real-time multi-user UI updates
- Sampling, rate limiting
- Kubernetes deployment docs
- Cursor-based pagination (may be pulled forward if pilot-scale data makes offset painful)

### Ongoing background — every version

Not batched into a "polish release." Addressed as pain points surface while building v2, v3, v4.

- Keyboard shortcuts for triage
- Saved views / custom filters
- Light theme
- Mobile reviewer experience
- Payload search upgrade (tsvector + GIN)
- Incremental data model improvements

---

## Gates & decision points

Not dates — a sequence of decisions and what signals each one.

### Gate 1: Start v2 work
- **Signal:** Andrew's solo-dogfood on v1 feels productive; "I wish I had a second human in here" is the top unmet need.
- **Decision:** Stop iterating on v1, start v2 collab + triage development.
- **Owner:** Andrew.

### Gate 2: V2 feels complete
- **Signal:** Andrew + a test collaborator (real or self-played) can run the full capture → triage → annotate loop smoothly. All 5 heuristics tuned against real data. Branched-rewrite UI usable. Comments, mentions, assignments working.
- **Decision:** Start V3 directly, or pause for a 1–2 pilot invite.
- **Note:** Pilot handoff is *available* at this gate but not *required*. Depends on how the work feels.

### Gate 3: V3 feels complete — the loop closes
- **Signal:** Annotated failures produce useful output — preference-pair JSONL that trains a model delta you can measure, markdown summaries that make sense in Notion, permalinks that create useful Linear tickets.
- **Decision:** Pick V4 (dev loop) vs. skip to V5 (ecosystem) vs. go straight to OSS launch prep.
- **Current read:** V4 before V5 — replay and diff amplify V3's export and strengthen the engineer-facing pitch.

### Gate 4: OSS launch readiness
- **Signal:** Feature surface feels complete enough to hand to strangers. Full improvement loop built out. At least one non-OpenAI framework integration. Onboarding docs. Single-deployment polish solid.
- **Decision:** Launch publicly. Ship with an "I want cloud — let me know when it's ready" signup form on `langperf.com`.
- **Purpose:** Feature-completeness *plus* a demand signal for cloud.

### Gate 5: Cloud work starts
- **Signal:** The "I want cloud" signup list hits a threshold Andrew is comfortable with.
- **Decision:** Begin cloud / SaaS work — multi-tenancy, SSO, audit logs, managed hosting.
- **Note:** This is the company-launch gate, not a product gate.

---

## Open design questions deferred to V2 implementation planning

These are specifically *not* resolved here and belong in the V2 implementation plan:

- Auth mechanism: email+password vs. magic-link vs. both
- Notification channel: in-app only vs. in-app + email
- Branched-rewrite storage format (data model decision; affects V3 export shape)
- Failure-mode taxonomy: fixed set vs. configurable per deployment
- Triage queue prioritization: heuristic-score composition and tiebreakers
- Cluster algorithm: exact-match on heuristic signature vs. approximate grouping
- Shared-link access control: token-scoped vs. session-based
- Degraded single-user mode: explicit flag vs. auto-detect from deployment state

---

## References

- `docs/vision.md` — full product vision
- `docs/ROADMAP.md` — complete v1 vs. v2+ bucket list
- `docs/superpowers/specs/2026-04-17-ui-shell-and-agent-first-class-design.md` — most recent v1 design spec

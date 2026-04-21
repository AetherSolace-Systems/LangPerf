# Sentinel — Defense Pivot Design

**Status:** Strategic parent spec. Defines product identity, architecture, load-bearing invariants, testing philosophy, and spec decomposition for the defense-vertical product built on the LangPerf engine.
**Date:** 2026-04-21
**Scope:** The full pivot. Not additive. Not an OSS feature set.

> This spec is the parent. Every subsystem named here gets its own child spec before implementation. Implementation plans do not come from this document directly — they come from the child specs. See "Build Sequence & Spec Decomposition."

---

## Posture

- **Full pivot.** LangPerf OSS is frozen as of 2026-04-21. No further OSS releases. Codebase remains as archival reference. Sentinel is a new, closed-source product developed in a private repository.
- **Motivation.** SBIR Phase I/II funding, DIU CSO (OTA) engagements, prime subcontracts. Not commercial self-serve; not OSS funnel.
- **Quality stance.** No deadline, no budget. Build the platform right the first time. Aligned with the v2 roadmap's "do it right" posture: good data model, well-considered abstractions, full design surface, not "everything and the kitchen sink."
- **First external artifact is the product itself.** No demo-theater. No thin prototype. We build the platform end-to-end before any pitch, SBIR submission, or public surface.
- **Cold pre-outreach.** No topic-specific SBIR commitment yet, no fielded DoD relationship. Architecture must be credible to a composite CDAO / acquisition reviewer without bending to any single topic's exact wording.

---

## Product Identity

- **Name (placeholder):** Sentinel. Real name + trademark clearance is an open question (see Open Questions). "Sentinel" collides with Microsoft's SIEM and other marks; final name selection deferred.
- **Tagline:** AI Agent Governance & Audit — the safest way to monitor and operationalize your AI agent workloads.
- **Category:** AI Agent Assurance Platform. Intentionally distinct from "LLM observability" (Langsmith, Langfuse, Arize) — the buyer cares about governance and evidence, not debugging.
- **One-line pitch:** A vendor-neutral governance and audit layer for AI agents operating in DoD and federal environments. Plug in the SDK and every agent action becomes a signed, policy-evaluated, audit-ready record — ready for ATO packages, contract audits, and responsible-AI oversight.

### Buyer personas (Phase 1 focus)

- **CDAO / Service Responsible-AI Lead.** Pain: must demonstrate NIST AI RMF + DoD RAI principle compliance for fielded AI systems, no tooling exists. Cares about evidence packs, policy enforcement, vendor-neutral horizontal coverage. Pitch fit: horizontal assurance platform.
- **Acquisition PMO / Contracting AI user.** Pain: using LLM agents for contract drafting/review/RFP response, no audit trail regulators or IG will accept. Cares about tamper-evident logs, FAR/DFARS policy compliance, human sign-off attestation. Pitch fit: the governance plane for agentic workflows in acquisition.

Both personas run concurrently on the same platform — one engine, two evidence-pack flavors, two pitch narratives.

### Explicit non-buyers (Phase 1)

- Tactical / edge / JADC2 operators — DDIL design is preserved, but tactical is not the lead market.
- IC agencies (NSA, DIA, NGA, CCMD J2s) — classification-aware data handling is a later phase.
- Civilian federal (VA, IRS, HHS) — FedRAMP path is deferred; civilian buyers come post-Phase II.

### Competitive posture

| Competitor | How we differ |
|---|---|
| UiPath AI Trust Layer | We are cross-vendor. They cover UiPath agents only. |
| Credo AI / Holistic AI / Fiddler | We are DoD-native: signed audit, policy-as-code, on-prem/air-gap from day one. They are commercial-governance tools with federal as an afterthought. |
| Scale AI / Anduril / Palantir AI | They sell agents. We govern agents from any vendor — a Switzerland position. |
| SIEM (Splunk, Elastic, Microsoft Sentinel) | SIEM is agent-semantics-blind. We understand trajectories, tool calls, reasoning. SIEM is a *destination* we export to, not a peer. |

### Partnership channel (GTM only)

UiPath — warm channel into shared acquisition customers. No technical dependency. UiPath is not a first-class connector, not in the critical path, and not mentioned in architecture beyond this line.

---

## Architecture

### Subsystems

Eleven subsystems, each with one clear purpose and a stable interface. Named after what the buyer sees, not after the plumbing.

1. **Capture SDK(s).** Agent-side library. Python first (hardening the existing `langperf` SDK and renaming), TypeScript second. Stable OTLP-based wire protocol with a `sentinel.*` attribute namespace. Source-side signing (FIPS-eligible) and offline store-and-forward queue for DDIL/air-gap. Framework connectors (Claude Agent SDK, OpenAI Agents SDK, LangChain/LangGraph) ship as peer packages.

2. **Ingest & Normalization.** Hot-path OTLP receiver. Verifies agent signatures, writes audit entry synchronously, enqueues for async processing, returns 200. No "unsigned data" path exists. Async processing is an implementation detail, not a product surface.

3. **Signed Audit Log.** Tamper-evident Merkle-chained log of every trajectory, node, policy evaluation, annotation, approval, override, and evidence-pack render. Append-only. Pluggable FIPS-capable crypto. External anchor support: periodic Merkle-root attestation to a customer-chosen witness (internal PKI / TSA / offline signer). This is the load-bearing trust primitive — the thing auditors accept.

4. **Agents-in-Action — Live Governance Console.** Live state-tracked view of every known agent. Finite state machine: `active`, `waiting_on_subagent`, `waiting_on_human`, `waiting_on_tool`, `blocked_by_policy`, `marked_for_review`, `paused`, `completed`, `failed`. State transitions are signed audit entries. UI shape: realtime board grouped by state, with `waiting_on_human` and `blocked_by_policy` as high-priority lanes. This is the primary operations surface for governance officers.

5. **Policy Engine.** Policy-as-code DSL (OPA/Rego assumed; validated in child spec). Versioned, signed bundles. Sync evaluation hook for high-severity policies; async worker evaluation for the rest. Ships with starter bundles: DoD RAI, NIST AI RMF subset, FAR/DFARS contract-review, basic prompt-injection heuristics. Policies are first-class data: versioned, signed, portable between deployments.

6. **HITL Approvals.** Peer subsystem to Policy — shares the decision model but has its own workflow and attestation data model. Three modes: **human-before-the-loop** (approve the agent config), **human-in-the-loop** (per-action approval, agent blocks), **human-on-the-loop** (agent proceeds by default, human has N seconds to intervene). Native two-person integrity (TPI) with role/ABAC constraints. DDIL/offline approvals via local CAC-reader identities, reconciled on reconnect. SDK primitive: `sentinel.request_approval(action, context, timeout=..., policy_id=...)` — `timeout` is a required keyword argument, no default, `None` allowed as explicit "wait forever." Missing `timeout=` raises `TimeoutNotSpecifiedError` at call time. Pre-deploy linter enforces.

7. **Evidence Pack Renderer.** Templating engine that takes `(trajectory window, policy evaluations, audit chain proofs, human attestations)` and renders artifacts: human-readable PDF, machine-readable JSON, OSCAL where applicable. Templates are versioned and signed. Launch template set: CDAO RAI evidence pack, NIST AI RMF profile pack, FAR/DFARS contract-review pack, generic audit pack. Packs are self-contained — verifiable offline with no live system access.

8. **Governance UI.** Extends the trajectory/triage UI surface with Policy, Evidence, Approvals, and Active-Agents surfaces. Next.js 14 App Router + TypeScript + Tailwind (unchanged stack). Rebranded token set.

9. **Identity & Access.** SAML + OIDC, CAC/PIV via DoD broker. RBAC from day one; data model is ABAC-ready (attributes on users, resources, policies) so classification/need-to-know lands later without migration. No password-only auth path in gov builds.

10. **Deployment & Supply Chain.** Five profiles from one codebase: `dev` (docker compose), `on-prem-single` (binary or compose), `on-prem-ha` (k8s + Postgres + object store), `air-gap` (offline installer bundle, local registry, no external dependencies), `il4-hosted` (partner deployment — Oracle Gov or AWS GovCloud, selection in Open Questions). SBOM (SPDX + CycloneDX) generated per release; artifacts Cosign-signed; STIG baselines applied to container images.

11. **Export & Downstream.** SIEM export (CEF / LEEF / JSON to Splunk, Elastic, Microsoft Sentinel), evidence-pack export (S3-compatible, signed URLs), incident hooks (webhook + Slack + Teams + Jira). All export operations are themselves recorded in the audit log.

### Subsystem relationships (critical path)

```
audit-chain ──▶ ingest ──▶ policy-engine ──┬─▶ hitl-approvals ──▶ governance-ui
    │                │                     │                          │
    └──▶ agent-id ───┘                     └─▶ evidence-renderer ─────┘
                                                    │
                           identity & access ───────┤
                                                    ▼
                                           deployment-profiles
                                                    │
                                                    ▼
                                          export & downstream
                                                    │
                                                    ▼
                                           policy-bundles-v1 (content)
```

Agent identity + audit chain are the first real work. Ingest hardening second. Everything else parallelizes with adequate staffing.

### Agent Identity (foundational)

Every agent has a cryptographic identity — a signing key pair bound to:

- the human principal who configured it,
- the tenant/org/program it belongs to,
- its approved configuration hash (prompt, tool set, model version, policy bundle references).

Every SDK-emitted span is signed with the agent's key. Every audit entry binds the relevant principals: `configured_by` (human, config-time), `executed_by` (agent, runtime), `attested_by` (human, approval-time). This is the non-repudiation backbone. Without it, audit is only as trustworthy as the ingest endpoint, which is not good enough for gov.

Config changes produce a new agent identity (new key, new config hash). Old identity is revoked, but its audit trail is preserved forever. "Did agent v2.3.1 do this" is verifiable indefinitely.

### What changes vs v2

- `api/app/services/*` — new services for `audit`, `policy`, `evidence`, `attestation`, `identity`, `approval`. Existing `trajectory`, `node`, `heuristic`, `tag` services retained but their writes now flow through audit.
- `api/app/otlp/ingest.py` — extended for synchronous audit write + async enqueue. Non-negotiable: no ingest path exists without audit.
- `sdk/` — renamed/rebranded, moved to its own private repo once stable (per existing extraction checklist). New connectors added as peer packages.
- `web/` — new routes under `/policy`, `/evidence`, `/attest`, `/active`. Existing `/trajectories` retained. Token rebrand.
- `alembic/` — additive migrations only (existing project rule).
- New top-level directories: `verifier/` (offline evidence verifier CLI), `policy-bundles/` (shipped bundles), `evidence-templates/` (shipped templates), `connectors/` (framework connectors), `deployment/` (installer scripts, profile configs).

### What does NOT change

- Python 3.12 + FastAPI + async SQLAlchemy 2.0 + Alembic + Postgres on the server.
- Next.js 14 App Router + TypeScript + Tailwind on the web.
- OTLP/HTTP as the wire protocol (extended, not replaced).
- Service-layer discipline from CLAUDE.md (thin routes, SQL + permission logic in services).

---

## Load-Bearing Invariants

Seven invariants the whole design rests on. Every child spec must preserve these.

1. **No data path bypasses the audit log.** Every ingested event has an audit entry written synchronously during request handling, before the queue accepts it. Workers verify audit-chain integrity before any mutation. An event that fails audit verification is quarantined and never persisted.
2. **Audit-synchronous-at-ingest.** Persistence is async, audit is not. The 200 OK is a commitment that the event is audited, not that it is persisted. A Postgres outage cannot cause audit loss.
3. **Every principal is cryptographic.** Agents have keys, humans have CACs, evidence packs bind all three. No anonymous writes in gov builds.
4. **Policies and evidence templates are data, not code.** Versioned, signed, user-installable, portable between deployments.
5. **Policies and overrides are both first-class.** The system is not "secure because it blocks everything"; it is "secure because every block *and* every override is accountable." Overrides require role-qualified CAC attestation and a reason string, and appear prominently in evidence packs.
6. **Retention is tiered and asymmetric.** Live console default 7 days (configurable to 30 / 90 / custom). Audit log forever. Trajectory data per-deployment retention policy, archived to cold storage beyond window. Three different durability tiers on purpose. No replay — audit is the forensic source of truth.
7. **One codebase, many deployment profiles.** No "gov fork." Features gate on profile, not on a separate branch. Offline/DDIL flows re-use the same crypto primitives; reconciliation is an expected state transition, not an error case.

---

## Key Flows

Four scenarios traced through the subsystems. These are the flows every child spec must remain consistent with.

### Flow 1 — Happy Path Ingest

1. SDK emits span, signs with agent key, sends OTLP request.
2. Ingest verifies agent signature against the agent identity registry. Invalid → quarantine, 401, audit entry of rejection.
3. Ingest writes audit entry synchronously: `(event_hash, agent_sig, ingest_sig, prev_audit_hash, timestamp)` linked into the Merkle chain. Load-bearing step — nothing else happens until audit is persisted.
4. Ingest enqueues raw event for async processing, returns 200.
5. Persistence worker consumes, verifies audit entry hash matches event hash, writes trajectory/span rows to Postgres.
6. Policy worker evaluates applicable policies against the span. Emits signed `PolicyEvaluation` rows. Happy path: no violations.
7. Live Console subscribes to state-change events (Postgres `LISTEN/NOTIFY` in small deployments, NATS subjects in HA). Agent transitions to `active`; dashboards update.

### Flow 2 — HITL Approval with Two-Person Integrity

Agent needs to execute a financially-significant action. Policy requires 2-of-3 approvers, at least one with `role:contracting_officer`.

1. Agent calls `sentinel.request_approval(action, context, timeout=900, policy_id="tpi-financial-v1")`. Blocks.
2. Sentinel creates `ApprovalRequest` (signed, audit-logged), evaluates `ApprovalPolicy` → TPI rule + role constraint.
3. Request routes to `ApproverGroup` via web UI + email + CAC prompt.
4. Approver A: allow (CAC-signed, audit entry).
5. Approver B: allow (CAC-signed, role=CO, audit entry). TPI threshold met.
6. Sentinel issues `ApprovalDecision` (signed, binds `action ↔ A.attest + B.attest`).
7. Agent receives `allow, decision_id`. Next action span carries `approval_decision_id`, binding the action cryptographically to the attestations.
8. Timeout elapses before threshold met → Decision = `timeout`, agent receives `deny` (fail-closed) unless policy specifies `fail-open` (rare in gov).
9. DDIL variant: upstream unreachable → approval routes to local CAC-reader endpoint using locally-stored `ApproverGroup` subset. Attestations queue; on reconnect, they merge into canonical audit chain via timestamps + local-node signatures.

### Flow 3 — Policy Violation → Hard Block → Override

Contract-review agent is about to attach a draft clause that the `far-dfars-v3` bundle classifies as non-compliant (missing 52.204-21 cybersecurity reference).

1. Agent emits span describing intended tool call: `attach_clause(clause_id=...)`.
2. Policy worker evaluates, finds violation (severity `hard_block`).
3. Policy worker writes signed `Violation` row, emits `block` event.
4. Ingest/SDK control channel receives block → on agent's next `sentinel.checkpoint()` call (or proactive push for SDKs that support it), agent receives `blocked_by_policy`, exception raised.
5. Live Console shows agent in `blocked_by_policy` column with policy reference + violation payload.
6. Reviewer with `role:contract_compliance` opens the agent, reviews evidence, either:
   - **Accepts the block** → agent terminates, incident logged, trajectory marked failed.
   - **Overrides the block** → issues signed `PolicyOverride` attestation (CAC + reason + policy exception reference). Agent resumes; override is bound to the action in audit. Overrides appear prominently in evidence packs.

### Flow 4 — Evidence Pack Generation & External Verification

Program manager needs to produce an ATO-package artifact covering all fielded agents for Q1.

1. PM opens Governance UI → Evidence → selects `CDAO-RAI-v1` template, scope `program_id:X, time_range:2026-01-01..03-31`.
2. Renderer queries: trajectories for scoped agents in window; policy evaluations + violations + overrides; approval decisions with attestations; audit-chain segments covering the window; agent config versions active in the window with their approval history.
3. Renderer assembles: human-readable PDF (program summary, compliance stats, flagged incidents with resolution, sample trajectories, attestation log), machine-readable JSON (OSCAL where applicable), audit-chain proof segment (Merkle proofs for every cited event, external-anchor attestation).
4. Evidence pack itself is signed (platform key + rendering-user's CAC). Generation is audit-logged. Artifact is exportable (signed URL or disk).
5. External auditor opens pack offline with the `sentinel-verify` CLI: verifies Merkle proofs against external anchor, verifies every cited attestation is CAC-signed by the claimed principal, verifies pack's own signature. No live system access required — critical for cross-organizational audits.

---

## Testing & Verification Strategy

Standard unit/integration tests are insufficient. A governance product must *prove* its integrity claims to external reviewers. Testing is layered.

### Layer 1 — Unit + integration
Existing discipline (pytest for api/sdk, vitest for web unit, Playwright for E2E). Every subsystem ships with its own suite. No subsystem merges without >90% coverage of its public interfaces.

### Layer 2 — Audit integrity (property-based)
- **Tamper detection.** Mutate any byte of any persisted audit entry; prove verification fails at the earliest affected segment. Exhaustive.
- **Chain continuity.** For any prefix of N audit entries, the Merkle root computed from scratch equals the persisted root.
- **External anchor roundtrip.** Emit root → attest → later verify a cited event against the anchor offline.
- **Concurrent write safety.** N writers × M entries, final chain is well-ordered, no duplicates, no gaps.

Run on every PR. A failure is treated as a security incident.

### Layer 3 — Policy engine correctness
- **Golden set per bundle.** Fixtures of `(trajectory, expected violations)` pairs covering true-positive and true-negative cases for every shipped bundle (DoD RAI, NIST AI RMF, FAR/DFARS). Bundle changes must keep the golden set green.
- **Differential testing across DSL versions.** When the DSL upgrades, run both evaluators against the golden set; divergence fails CI.
- **Mutation testing.** Mutate a policy by a small diff; verify the golden set catches the regression on at least one case. Gap in coverage → fail.

### Layer 4 — Evidence pack verification
- **Deterministic rendering.** Identical inputs produce byte-identical output. CI-enforced.
- **Offline verifier CLI (`sentinel-verify`).** Separate, minimal codebase. Same tool we give to auditors runs on every E2E-generated pack in CI.

### Layer 5 — End-to-end buyer-flavored scenarios (nightly)
- **Scenario A — CDAO RAI evidence.** 50 simulated runs, seeded violations + overrides → RAI evidence pack → verifier passes → content asserts expected elements.
- **Scenario D — Acquisition contract review.** Simulated agent, FAR/DFARS bundle active, hard-block + CO-role override → engagement evidence pack → verifier passes.
- **Scenario HITL-TPI.** High-impact action, 2-of-3 with role constraint, scripted CAC attestations → action proceeds → audit chain reconstructs TPI path.

### Layer 6 — Adversarial / chaos (quarterly or per-release)
- Audit tamper attempts on live dev deployment.
- Forged / revoked agent signatures.
- DDIL reconciliation after simulated partition.
- Systematic policy-bypass attempts (regex holes, context exhaustion, encoding tricks).

### Layer 7 — External review
- Third-party pentest before any gov pilot. Results packaged for SBIR / ATO submissions.
- Formal threat model doc per subsystem (STRIDE-style), reviewed each release.
- Cryptographic review of audit chain + agent identity subsystems by an external reviewer before any prod deployment.

### Explicitly deferred
- Full FIPS 140-3 module validation. We use FIPS-validated libraries from day one; formal module validation happens at IL4-ready milestone.
- cATO / continuous-ATO automation. Evidence packs support ATO submissions; eMASS automation is a later phase.
- Red-team-as-a-service integrations. Planned; not scoped now.

---

## Build Sequence & Spec Decomposition

This spec is too large for a single implementation plan. It is the strategic parent. Each subsystem gets its own child spec before implementation.

### Child specs, dependency order

The first two are prerequisites for everything else. After that, significant parallelism is possible.

1. **`sentinel-audit-chain-and-agent-identity`** — Merkle log, signing, verification, agent key issuance + registry, signed SDK events, external anchor. Foundation. Nothing else can be built without this.
2. **`sentinel-ingest-and-async-processing`** — two-stage ingest, audit-synchronous enforcement, pluggable queue (Postgres SKIP LOCKED → NATS JetStream), worker model.
3. **`sentinel-policy-engine`** — DSL selection validation, bundle/version/signing model, evaluation workers, golden-set testing harness.
4. **`sentinel-hitl-approvals`** — `ApprovalRequest` / `ApprovalDecision` data model, SDK primitive with required `timeout`, TPI, routing, channels, DDIL reconciliation.
5. **`sentinel-agents-in-action-console`** — live state tracker, state machine, UI, retention model.
6. **`sentinel-evidence-renderer`** — templating engine, OSCAL integration, deterministic rendering, offline verifier CLI, first templates.
7. **`sentinel-identity-and-access`** — SAML/OIDC, CAC/PIV, RBAC now, ABAC-ready data model.
8. **`sentinel-governance-ui`** — Policy + Evidence + Approvals + Active-Agents surfaces, rebrand.
9. **`sentinel-export-and-downstream`** — SIEM export (CEF/LEEF/JSON), webhooks, incident hooks.
10. **`sentinel-deployment-profiles`** — dev, on-prem-single, on-prem-HA, air-gap installer, IL4-hosted partner prep. STIG baselines, SBOM, Cosign signing.
11. **`sentinel-policy-bundles-v1`** — policy content: DoD RAI, NIST AI RMF subset, FAR/DFARS contract-review. Content work is substantively different from engine work.
12. **`sentinel-sdk-and-connectors`** — SDK hardening, TypeScript SDK, framework connectors (Claude Agent SDK, OpenAI Agents SDK, LangChain/LangGraph). Can parallel much of the above once wire protocol is stable.

### Rebrand + close-source tasks (before any external artifact)

- Product name chosen + trademark cleared.
- Repo split: gov product in private org; OSS LangPerf frozen permanently.
- Web tokens, domains, legal (BAA-ready, export-control review).
- Clean separation of "LangPerf OSS" history from "Sentinel" history to avoid OSS-license pollution in the closed codebase.

---

## Deployment Profiles

One codebase, five profiles. Feature gates on profile, not branch.

| Profile | Purpose | Infrastructure |
|---|---|---|
| `dev` | Local development | docker compose, no external deps |
| `on-prem-single` | Small deployment / evaluation | single binary or compose stack |
| `on-prem-ha` | Production on-prem | k8s + Postgres + object store + NATS |
| `air-gap` | No-network deployments | offline installer bundle, local registry, no external deps |
| `il4-hosted` | DoD-hosted via partner | Oracle Gov or AWS GovCloud (partner TBD) |

All profiles ship SBOM (SPDX + CycloneDX), Cosign-signed artifacts, STIG-baselined container images.

---

## Funding & GTM Path

### Funding sequence

1. **Platform ready → topic hunting.** Sentinel reaches Phase 1 subsystem completeness → submissions to AFWERX / Army xTech / DIU CSO Open Topics where the platform fits.
2. **SBIR Phase I (~$250K, 6mo).** Feasibility study against a specific topic. Narrative: "platform exists; this Phase I proves feasibility against your scenario."
3. **SBIR Phase II (~$1–2M, 2yr).** Funds IL4 hardening, STIG compliance, cATO artifacts, FIPS module validation.
4. **Phase III / OTA / subcontract (uncapped).** Transition to prime subcontract or direct agency engagement.

### Topic-hunting sources to monitor

- AFWERX Open Topic cycles
- CDAO SBIR topics (DoD SBIR.mil + CDAO direct)
- DIU Commercial Solutions Opening (CSO) calls
- Army xTech quarterly
- SOCOM SOFWERX prize challenges
- AFRL RAI-specific topics
- Tradewinds Solutions Marketplace (post-MVP listing)

### Warm channels

- **UiPath partnership.** Acquisition-vertical warm intros via shared customers. GTM-only; no technical dependency.

### What we are NOT targeting (Phase 1/2)

- Classified work (needs facility clearance; later phase).
- Full FedRAMP certification (18mo+ process; post-Phase II).
- Cloud SaaS for DoD (needs IL4 minimum; post-Phase II).

---

## Open Questions

To resolve before or during the relevant child spec.

- **Final product name + trademark clearance.** "Sentinel" is a placeholder; collides with Microsoft's SIEM. Name selection is not gating architecture but gates any external artifact.
- **Policy DSL.** OPA/Rego assumed. Validated in `sentinel-policy-engine` child spec — alternatives (Cedar, custom) evaluated there.
- **External anchor technology.** Internal PKI vs. RFC 3161 TSA vs. offline file-signer vs. other. Evaluated in `sentinel-audit-chain-and-agent-identity`.
- **FIPS-validated crypto library.** openssl-FIPS vs. AWS-LC-FIPS vs. libsodium-FIPS. Evaluated in audit-chain spec.
- **IL4 hosting partner.** Oracle Gov vs. AWS GovCloud vs. Azure Gov. Evaluated in `sentinel-deployment-profiles`.
- **HITL notification channels.** Web + email baseline. Slack/Teams for non-classified? Mobile push? Evaluated in `sentinel-hitl-approvals`.
- **Evidence pack template set.** Launch set is CDAO RAI + NIST AI RMF + FAR/DFARS + generic. Expansion list (OSCAL profiles, cATO-specific) deferred to `sentinel-evidence-renderer`.
- **Queue backend at scale.** NATS JetStream baseline for HA. Kafka interface preserved but not built.
- **SDK name.** `langperf` → TBD. Aligns with final product name decision.

---

## Deferred (not in this pivot)

- OSS development. LangPerf OSS is frozen permanently.
- SaaS / managed cloud offering. Post-Phase II, demand-gated.
- Classified (SECRET+) deployment.
- Intel community (IC) vertical features (classification propagation, cross-domain leak detection).
- Tactical / edge / JADC2 as primary use case. Architecture preserves DDIL support; tactical is not the lead market.
- cATO automation (eMASS integration).
- Full FedRAMP certification path.
- Civilian federal (VA, IRS, HHS) GTM motion.

---

## References

- `docs/vision.md` — original product vision (OSS era, archival).
- `docs/ROADMAP.md` — OSS roadmap (archival).
- `docs/superpowers/specs/2026-04-17-langperf-v2-dev-roadmap.md` — v2 dev roadmap (archival).
- `docs/superpowers/specs/2026-04-17-ui-shell-and-agent-first-class-design.md` — v1 UI shell design (many concepts carry over).
- `CLAUDE.md` — project working instructions.

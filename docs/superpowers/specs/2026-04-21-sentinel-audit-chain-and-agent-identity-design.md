# Sentinel — Audit Chain & Agent Identity Design

**Status:** Child spec. First in the dependency order from `2026-04-21-sentinel-defense-pivot-design.md`. Everything else is blocked on this.
**Date:** 2026-04-21
**Parent spec:** `docs/superpowers/specs/2026-04-21-sentinel-defense-pivot-design.md`
**Scope:** The foundational trust primitives: signed Merkle audit log, external anchoring, agent cryptographic identity, ingest-node identity, and the offline verifier contract.

> This spec is sized for a single implementation plan — large, but coherent. Audit log and agent identity are tightly coupled (agent keys sign events that enter the audit log; agent lifecycle events are themselves audit entries). Splitting them would double the coordination cost.

---

## Posture & Scope

- **Foundation for everything.** Ingest, policy, HITL approvals, evidence rendering, export — all read from or write to the audit chain and depend on cryptographic principals. This child spec lands first.
- **Approach 2 from the parent spec.** Native Python Merkle transparency log, patterned on RFC 6962 / Trillian / Rekor. Vetted crypto primitives only (`pynacl`, `cryptography`). No hand-rolled crypto.
- **No deadline, build it right.** Aligned with the parent spec's quality stance.
- **Performance target.** `<10ms p99` audit-write latency at `up to 10K events/sec aggregate`. Achieved via single-Writer micro-batching, not per-request advisory locking.
- **Deployment-agnostic.** Works in `dev`, `on-prem-single`, `on-prem-ha`, `air-gap`, and `il4-hosted` profiles from day one. Feature gates are by profile, not by branch.

### What this spec covers

- Data model: `audit_entries`, `audit_roots`, `external_anchors`, `agent_identities`, `ingest_nodes`, and cross-reference columns on existing trajectory/span tables.
- Write path: ingest → verify → batch → append → snapshot → anchor.
- Merkle tree construction (RFC 6962-style).
- Agent identity lifecycle: issuance, signing, revocation, multi-instance handling.
- Ingest node identity.
- Verifier CLI contract (`sentinel-verify`).
- Integration surface: services, SDK additions, migrations.
- Testing hooks, open questions, deferred items.

### What this spec does NOT cover

- Policy engine (Subsystem 5 — separate child spec).
- HITL approval workflow beyond the "human-before-the-loop agent-config approval" touchpoint (Subsystem 6 — separate child spec, which will build on the `AuditService.append` contract declared here).
- Evidence pack rendering (Subsystem 7 — separate child spec, consumes proofs and anchors defined here).
- Governance UI (Subsystem 8 — separate child spec).
- CAC/PIV middleware selection (Subsystem 9 — separate child spec; we assume an abstract CAC-signature verifier here).

---

## Data Model

### `audit_entries` — the log

| Column | Type | Notes |
|---|---|---|
| `id` | `bigserial` PK | Surrogate; `seq` is the logical identifier |
| `seq` | `bigint` UNIQUE NOT NULL | Strictly monotonic, gapless; allocated under in-process lock in the single Writer |
| `prev_hash` | `bytea(32)` NOT NULL | `entry_hash` of `seq-1`; zero-bytes for genesis |
| `event_type` | `text` NOT NULL | Enum-constrained (see below) |
| `event_payload` | `bytea` NOT NULL | Canonical JCS (RFC 8785) serialization |
| `event_hash` | `bytea(32)` NOT NULL | SHA-256 of `event_payload` |
| `entry_hash` | `bytea(32)` NOT NULL | SHA-256 of `(seq ‖ prev_hash ‖ event_hash ‖ agent_id ‖ principal_human_id ‖ ts ‖ agent_signature ‖ ingest_signature)` |
| `agent_id` | `uuid` FK → `agent_identities.id`, NULL OK | Set iff event was SDK-emitted |
| `principal_human_id` | `uuid` FK → `users.id`, NULL OK | Set for human-originated events |
| `agent_signature` | `bytea`, NULL OK | Agent's signature over `event_payload`; NULL iff `agent_id` is NULL |
| `ingest_node_id` | `uuid` FK → `ingest_nodes.id` NOT NULL | |
| `ingest_signature` | `bytea` NOT NULL | Ingest node signs `(seq ‖ prev_hash ‖ event_hash ‖ agent_signature)` |
| `ts` | `timestamptz` NOT NULL DEFAULT `now()` | Server-side ingest timestamp |
| `agent_ts` | `timestamptz`, NULL OK | Agent-claimed timestamp if present |

Indexes: `UNIQUE(seq)`, `(event_type, ts)`, `(agent_id, ts)`, `(principal_human_id, ts)`.

**Enum values for `event_type`:** `span.ingest`, `span.reject`, `policy.eval`, `policy.violation`, `policy.override`, `approval.request`, `approval.decision`, `agent.propose`, `agent.approve`, `agent.issue`, `agent.revoke`, `ingest.register`, `ingest.retire`, `evidence.render`, `config.change`, `anchor.emit`. New types added via migration + enum expansion.

**UPDATE/DELETE denied** via Postgres trigger and role grant. The service DB role has `INSERT, SELECT` only. Schema-modification role is separate and used only by Alembic.

### `audit_roots` — periodic Merkle snapshots

| Column | Type | Notes |
|---|---|---|
| `id` | `bigserial` PK | |
| `tree_size` | `bigint` UNIQUE NOT NULL | Entries `[0, tree_size)` covered |
| `root_hash` | `bytea(32)` NOT NULL | Merkle root using RFC 6962 hashing |
| `computed_at` | `timestamptz` NOT NULL | |
| `ingest_node_id` | `uuid` FK NOT NULL | |
| `ingest_signature` | `bytea` NOT NULL | Signed `(tree_size ‖ root_hash)` |

Roots computed on whichever triggers first: every `N` entries (default `N=1000`), every `M` seconds (default `M=60s`), or render-time before an evidence pack is assembled.

### `external_anchors` — external witness attestations

| Column | Type | Notes |
|---|---|---|
| `id` | `bigserial` PK | |
| `root_id` | `bigint` FK → `audit_roots.id` NOT NULL | |
| `anchor_type` | `text` NOT NULL | `rfc3161_tsa` / `offline_file` / `internal_pki` / `none` (dev only) |
| `anchor_payload` | `bytea` NOT NULL | TSA response, signed file, or PKI attestation |
| `anchored_at` | `timestamptz` NOT NULL | |
| `anchor_ref` | `text`, NULL OK | Deployment-configured reference/URL of the authority |

Multiple anchor types per deployment supported. Rate-limited (default max 1 per 10s per type).

### `agent_identities` — agent cryptographic principals

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid` PK | |
| `public_key` | `bytea` NOT NULL | |
| `public_key_alg` | `text` NOT NULL | `ed25519` / `ecdsa-p384` |
| `config_hash` | `bytea(32)` NOT NULL | SHA-256 of canonical agent config |
| `config_ref` | `text` NOT NULL | Human-readable config reference / commit |
| `tenant_id` | `uuid` FK → `tenants.id` NOT NULL | |
| `owner_human_id` | `uuid` FK → `users.id` NOT NULL | |
| `issuance_audit_entry_id` | `bigint` FK → `audit_entries.id` NOT NULL | |
| `issued_at` | `timestamptz` NOT NULL | |
| `revoked_at` | `timestamptz`, NULL OK | |
| `revocation_audit_entry_id` | `bigint` FK → `audit_entries.id`, NULL OK | |
| `revocation_reason` | `text`, NULL OK | |

Indexes: `UNIQUE(public_key)`, `(config_hash, tenant_id)` (non-unique — replicas share `config_hash`), `(owner_human_id)`.

**Note:** `config_hash + tenant_id` is intentionally not unique — per-replica keypair default means multiple rows per config.

### `ingest_nodes` — trusted ingest node registry

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid` PK | |
| `public_key` | `bytea` NOT NULL | |
| `public_key_alg` | `text` NOT NULL | |
| `key_storage` | `text` NOT NULL | `tpm` / `software_kms` / `hsm` |
| `tpm_ak_quote` | `bytea`, NULL OK | TPM 2.0 attestation key quote |
| `operator_human_id` | `uuid` FK → `users.id` NOT NULL | |
| `registration_audit_entry_id` | `bigint` FK → `audit_entries.id` NOT NULL | |
| `registered_at` | `timestamptz` NOT NULL | |
| `retired_at` | `timestamptz`, NULL OK | |

### Cross-reference from existing tables

`Trajectory`, `Node`, `HeuristicHit`, and future mutation-bearing tables get an `audit_entry_id` FK column (NULL OK during migration; required post-migration for new rows). This keeps the existing v2 schema intact while making every row traceable to its audit entry.

### Invariants on the data model

1. `audit_entries` is append-only. No UPDATE, no DELETE, no TRUNCATE. Enforced by trigger + role grants.
2. `seq` is strictly monotonic and gapless.
3. `entry.prev_hash == previous_entry.entry_hash` for all `seq > 0`.
4. Every agent-emitted event has a valid signature against the registered public key.
5. Agent identity rows never mutate. Revocation is `revoked_at` flip + a new `agent.revoke` audit entry.
6. Every entry carries an ingest signature from a registered, non-retired `ingest_nodes` row.
7. Canonical encoding is JCS (RFC 8785) forever; any change is a versioned wire-contract break.

### Phase-1 simplification

Parent spec mandates "one org per deployment." Phase 1 uses a **single global audit chain per deployment**. The `tenant_id` columns are future-proofing for multi-tenant deployments (post-Phase II).

---

## Write Path, Merkle Tree & Anchor Mechanics

### Write path (hot path)

```
Client OTLP ─┬─▶ Receiver (stateless, horizontally scalable)
             │       │
             │       │ 1. Parse OTLP batch
             │       │ 2. Extract sentinel.agent_id + sentinel.sig per span
             │       │ 3. Canonicalize event_payload (JCS, sig removed)
             │       │ 4. Verify agent_signature → invalid: span.reject + 401
             │       │ 5. Submit to in-process Writer; await confirmation
             │       │
             │       └──▶ Writer (single per deployment, chain-owning)
             │                │
             │                │ 6. Acquire in-memory chain lock
             │                │ 7. Batch up to N submissions or M ms
             │                │ 8. Per submission: allocate seq, compute entry_hash,
             │                │    sign with ingest node key
             │                │ 9. Single batched INSERT in one transaction
             │                │ 10. WAL commit (group commit)
             │                │ 11. Notify waiters with seq + entry_hash
             │                │
             │       ┌────◀───┘
             │       ▼
             │    12. Enqueue downstream processing (audit seq attached)
             │    13. 200 OK with per-span audit seqs
             ▼
        200 OK
```

### Why a single Writer

Per-request advisory-lock INSERTs won't hit `<10ms p99 at 10K/sec`. The Writer batches 50–500 events per transaction with group commit — ~20–200 transactions/sec at target volume, well within Postgres comfort. Exactly one Writer exists per deployment; HA is solved by leader election via a Postgres application-level advisory lock. A failover replaces the Writer; there is never concurrent Writers.

### Writer state and startup integrity check

The Writer maintains `last_seq` and `last_entry_hash` in memory, seeded at startup from `SELECT ... ORDER BY seq DESC LIMIT 1`. Before accepting submissions, the Writer recomputes `entry_hash` of the latest row from its stored columns and compares to the persisted value. Mismatch → the Writer refuses to start and raises a critical-severity integrity incident. DB tampering cannot silently corrupt the chain.

### Canonical encoding (JCS) specifics

- The `sentinel.sig` attribute is stripped before canonicalization.
- Timestamps canonicalize as ISO-8601 strings (not numbers — JCS number-encoding constraints).
- Unicode normalized to NFC.
- Golden-file tests of JCS output gate merges to the canonicalizer.

### Rejection handling

Invalid signatures, unknown/revoked agents, malformed payloads → a `span.reject` audit entry is written with the rejection reason (not the bad payload). Rate-limited per agent to prevent rejection-amplification attacks.

### Merkle tree (RFC 6962)

- **Leaf hash:** `H(0x00 ‖ entry_hash)` where `H = SHA-256`.
- **Internal node hash:** `H(0x01 ‖ left ‖ right)`.
- **Root `R(n)`:** hash over leaves `[0, n)`, left-heavy imperfect trees per RFC 6962 §2.1.

Domain separators `0x00` / `0x01` prevent leaf/internal collisions. Standard scheme — no bespoke crypto.

### Merkle tree storage (Phase 1)

- Leaves stored in `audit_entries.entry_hash` (already present).
- Roots stored in `audit_roots` (permanent).
- Internal nodes computed on demand with an in-memory LRU cache for warm-path proofs.
- Phase-2 optimization: add an `audit_tree_nodes` table if proof generation for 10M-leaf trees exceeds the 500ms evidence-pack budget. Not premature.

### Proof types

- **Inclusion proof** — proves leaf K is in tree of size N. RFC 6962 algorithm.
- **Consistency proof** — proves root of size N₁ is a prefix of root at size N₂. RFC 6962 algorithm.

Both in the `AuditService` interface (below). Verifier uses these offline.

### External anchor lifecycle

1. Writer snapshots a root → inserts `audit_roots`.
2. `anchor.emit` worker picks up the new root and attempts to anchor via the configured type(s).
3. Success → insert `external_anchors` + emit `anchor.emit` audit entry (anchoring is itself audited).
4. Failure → exponential backoff; after threshold, alert operator. Evidence packs in the unanchored window cite the last successful anchor and flag "window unanchored."

Multiple anchor types per deployment are supported as belt-and-suspenders.

### Anchor-type matrix

| Type | Valid in | Mechanism |
|---|---|---|
| `rfc3161_tsa` | Hosted w/ internet | POST root hash to configured TSA URL; store signed `TimeStampToken` |
| `offline_file` | Air-gap | Write root to a file; deployment-local signing process (smartcard, yubikey, PIV) signs; result stored |
| `internal_pki` | Enterprise / IL4 | Customer PKI endpoint signs root |
| `none` | `profile=dev` only | Skipped; production profiles reject this configuration at startup |

### Failure semantics

| Failure | Behavior |
|---|---|
| Agent signature invalid | `span.reject` entry; 401; rate-limited |
| Unknown / revoked agent | `span.reject` entry; 401 |
| Malformed payload | `span.reject` entry; 400 |
| Writer DB write fails | 500; event not accepted; client retries |
| Writer chain-state divergence at startup | Refuses to start; integrity incident |
| Merkle snapshot fails | Audit writes continue; snapshot retried; no hot-path impact |
| Anchor emission fails | Root persisted without anchor; retried; operator alerted after threshold |

**Load-bearing property:** a 200 OK from ingest is a commitment that the audit entry is persisted and the chain is intact. Snapshot + anchor are best-effort async; failures there cannot compromise the chain.

---

## Agent Identity Lifecycle

### Issuance — bootstrap-token + agent-side keypair

Private keys never transit the network. Pattern borrows from ACME and Vault-AppRole.

```
 Engineer              Sentinel              Approver            Agent Runtime
    │                     │                     │                     │
    │ submit config ────▶ │                     │                     │
    │                     │ compute config_hash │                     │
    │                     │ audit: config.change│                     │
    │                     │ ──── request ─────▶ │                     │
    │                     │                     │ review              │
    │                     │                     │ CAC-sign approve ─▶ │
    │                     │ ◀── agent.approve ──│                     │
    │                     │ issue bootstrap tok │                     │
    │                     │ (single-use, bound  │                     │
    │                     │  to config_hash)    │                     │
    │ ◀─── token ──────── │                     │                     │
    │                     │                     │                     │
    │ deploy with token ────────────────────────────────────────────▶ │
    │                     │                     │                     │ generate keypair
    │                     │                     │                     │ sign PoP w/ token
    │                     │ ◀── register ────────────────────────────│
    │                     │ verify PoP          │                     │
    │                     │ verify token fresh  │                     │
    │                     │ insert agent_id row │                     │
    │                     │ audit: agent.issue  │                     │
    │                     │ ─── ack + id ───────────────────────────▶ │
    │                     │                     │                     │ ready
```

- Bootstrap token is single-use, bound to a specific `config_hash`, TTL-bounded (default 24h).
- Proof-of-possession signs a challenge with the freshly-generated private key; replays and cross-config attempts are rejected.
- Approval is a human-before-the-loop operation — a peer mode of the HITL approval subsystem; same approver infrastructure.

### Agent-side key custody

Pluggable `KeyStore` abstraction, SDK-shipped:

| Backend | Default? | Use case |
|---|---|---|
| `FileKeyStore` | Yes | On-disk, `chmod 600`, optional passphrase |
| `EnvKeyStore` | No | CI/test only; discouraged |
| `OSKeyringKeyStore` | Opportunistic | macOS Keychain, Windows Credential Manager, libsecret |
| `TPMKeyStore` | Enterprise opt-in | TPM 2.0 sealed |
| `HSMKeyStore` | Enterprise opt-in | PKCS#11 |

SDK refuses to start with permissive key-file modes. Keys never logged. Lost key → revoke + re-issue.

### Signing scope

- Canonicalized span payload (JCS) with `sentinel.sig` removed.
- Signature placed in `sentinel.sig` as `base64(signature_bytes)`.
- Algorithm matches agent's `public_key_alg`.
- Only governance-relevant span fields canonicalize — field set defined in `sentinel/ATTRIBUTES.md` (successor to existing `langperf/ATTRIBUTES.md`). Stable post-1.0.

Ed25519 is fast enough (~50μs/sig) for per-span signing at target volumes. Batch/aggregate signing deferred.

### Revocation

Four triggers:

1. **Config change** — new `config_hash` → new identity → old `revoked_at` set with `reason=config_superseded`.
2. **Manual** — owner or role with `action:revoke_agent` issues CAC-signed `agent.revoke`. For suspected compromise.
3. **Inactivity policy** — auto-revoke after N days idle (default 90, configurable, disable-able).
4. **Policy-initiated** — policy violation with `remediation=revoke_agent`; `agent.revoke` with `reason=policy_remediation` + violation reference.

Post-revocation:
- Spans signed by revoked key after `revoked_at` → `span.reject`, 401.
- Past spans remain valid and verifiable forever.
- Re-issuance requires new config approval + new bootstrap token. No un-revoke.

### Multi-instance / replica handling

Default: **per-replica keypair, shared `config_hash`**. Each running instance has its own `agent_identities` row. Compromise of one replica does not compromise the deployment.

`(config_hash, tenant_id)` is a non-unique index — replicas share `config_hash` deliberately.

Operational tooling: `sentinel issue-token --config-hash=X --count=N` produces N single-use tokens for deployment systems (k8s operator, systemd unit) to inject one per replica.

### Ingest node identity

Ingest nodes have their own cryptographic identities (`ingest_nodes` table).

- Operator with `role:deployment_admin` registers a new ingest node via CAC-signed action.
- Node generates keypair on first boot; sealed to TPM where present, otherwise KMS-wrapped.
- Public key + TPM quote submitted to Sentinel.
- Operator verifies TPM quote against expected PCR set (deployment-configured baseline), approves, `ingest.register` audit entry written.

Retirement flow is symmetric to agent revocation.

---

## Verifier CLI Contract (`sentinel-verify`)

A small, auditor-facing CLI that verifies an evidence pack offline with no live system access.

### Inputs

- An evidence pack (file or directory) containing:
  - Cited `audit_entries` rows
  - `audit_roots` snapshots relevant to the pack's time window
  - `external_anchors` attestations for those roots
  - `agent_identities` public keys referenced by cited spans
  - `ingest_nodes` public keys
  - Merkle inclusion proofs for every cited entry
  - Where applicable: consistency proofs between cited roots
- Trust roots: anchor authority public keys / TSA cert chains / customer-PKI trust anchors. Shipped with the pack or supplied by the auditor.

### Checks performed

1. Every cited `audit_entries.entry_hash` recomputes correctly from its columns.
2. `prev_hash` chain continuity across cited segments.
3. Merkle inclusion proof for each cited entry → resulting root matches a cited `audit_roots.root_hash`.
4. `audit_roots.ingest_signature` verifies against the cited `ingest_nodes.public_key`.
5. Every cited root has at least one `external_anchors` attestation that verifies against the supplied trust roots.
6. Every cited span's `agent_signature` verifies against the cited `agent_identities.public_key` using the declared algorithm.
7. Every cited human attestation (approval / override / evidence-pack issuance) verifies against the relevant CAC public key + trust chain.
8. Consistency proofs between boundary roots are present and verify (when pack claims a time window).

### Output

- `PASS` with a machine-readable summary: counts by event type, time range, cited principals (agents, humans, ingest nodes).
- `FAIL` with the precise entry / signature / proof that failed and the reason. Silent failures are disallowed.

### Packaging

- Python package `sentinel-verify` on PyPI + gov-mirror equivalent.
- Self-contained; all crypto dependencies vendored.
- Cross-platform: Linux, macOS, Windows.
- Rust port deferred to Phase 2 pending distribution-friction signals.
- **Developed in a separate repository.** Hard rule: never depends on `api/` or server code. Its only shared surface is the canonical encoding spec and the public data schemas.

---

## Integration Surface

### API services (`api/app/services/`)

```
audit.py
  AuditService.append(event_type, payload, agent_id=None, principal_human_id=None) -> AuditEntry
  AuditService.get_by_seq(seq) -> AuditEntry
  AuditService.get_inclusion_proof(seq, tree_size) -> InclusionProof
  AuditService.get_consistency_proof(tree_size_1, tree_size_2) -> ConsistencyProof
  AuditService.recent_root() -> AuditRoot
  AuditService.emit_anchor(root_id) -> ExternalAnchor

agent_identity.py
  AgentIdentityService.propose_config(config, owner_id) -> ConfigProposal
  AgentIdentityService.approve_config(proposal_id, approver_id, cac_sig) -> BootstrapTokenSet
  AgentIdentityService.register_key(bootstrap_token, public_key, pop_signature) -> AgentIdentity
  AgentIdentityService.revoke(agent_id, reason, principal_id) -> AgentIdentity
  AgentIdentityService.get_by_public_key(pk) -> AgentIdentity | None

ingest_node.py
  IngestNodeService.register(public_key, alg, tpm_quote, operator_id) -> IngestNode
  IngestNodeService.retire(node_id, operator_id) -> IngestNode
```

`AuditService.append` is the single mutation entry-point for every other service. Every other service calls it before any non-audit write.

### Ingest path changes

`api/app/otlp/ingest.py`:

1. Extract + verify agent signatures per span.
2. Submit each span to the Writer via `AuditService.append()`.
3. Await the Writer's confirmation (`seq`, `entry_hash`) before returning 200.
4. Enqueue for async downstream processing with the audit seq attached.

### SDK additions (Python first; TypeScript follows in `sentinel-sdk-and-connectors`)

```
sentinel/identity.py     # KeyStore abstraction, bootstrap flow
sentinel/signing.py      # per-span signing, JCS canonicalization
sentinel/approval.py     # request_approval() primitive — signature declared; implementation in sentinel-hitl-approvals
```

Bootstrap CLI:

```
sentinel agent bootstrap --token=<bootstrap_token> --keystore=file:/path/to/key
```

Generates keypair, registers with the server, receives agent_id, writes `agent.issue` via server-side audit.

### Alembic migrations (additive only)

- `00XX_audit_tables.py` — `audit_entries`, `audit_roots`, `external_anchors` + append-only trigger
- `00XX_agent_identities.py` — `agent_identities`
- `00XX_ingest_nodes.py` — `ingest_nodes`
- `00XX_audit_entry_links.py` — `audit_entry_id` FK columns on existing `Trajectory`, `Node`, `HeuristicHit`

Migrations are append-only per project rule.

---

## Testing Hooks

Beyond the parent-spec Layer 2 property-based tests:

- **Writer batching invariant.** Property test across concurrent receivers: resulting `audit_entries` has strictly monotonic, gapless `seq` and correct `prev_hash` continuity under any interleaving.
- **Canonicalization determinism.** Golden-file tests of JCS output for reference span payloads.
- **Signature algorithm roundtrip.** For each supported algorithm (Ed25519, ECDSA P-384): sign → verify → serialize → deserialize → reverify.
- **Bootstrap token lifecycle.** Single-use, expires, scoped to `config_hash`, not replayable, not reusable across configs.
- **Revocation honored at ingest.** Property-tested across many `revoked_at` positions: post-revocation spans rejected, pre-revocation spans accepted.
- **Merkle-proof correctness vs reference.** Cross-check inclusion proofs against a reference implementation (e.g., `trillian` Python client's verifier).
- **Anchor attestation roundtrip.** For each anchor type: emit → anchor → fetch → verify → reject-on-tamper.
- **Startup integrity check.** Simulated DB corruption; Writer refuses to start.

---

## Open Questions

- **TSA vendor choice** for hosted default. DigiCert / GlobalSign / Sectigo all offer RFC 3161 TSA. Gov-friendly shortlist selected in implementation. Customer-overridable per deployment.
- **CAC/PIV signing library.** `python-pkcs11` vs `cryptography` + smartcard middleware vs higher-level wrappers. Decided in `sentinel-identity-and-access` child spec. This spec exposes the principal's public key and assumes an abstract CAC-signature verifier.
- **Ed25519 vs Ed448 for FIPS 186-5.** Both approved. Ed25519 unless a buyer specifies otherwise.
- **TPM attestation PCR baseline.** Expected PCR set (BIOS measurement, kernel hash, runtime hash) per deployment profile. Baseline PCR set provided in implementation.
- **Bootstrap token transport for air-gap.** Tokens may travel on removable media. Format is human-inspectable and replay-resistant (single-use enforced server-side). Detail in implementation.
- **Per-span signing cost at extreme burst.** Ed25519 is fast but ~10K signs/sec/process is a full core. SDK may need multi-process/multi-thread signing pool. Benchmarks in implementation.

---

## Deferred

- **Batch/aggregate signature schemes** on the SDK side. Not needed for Phase 1.
- **Agent-side TPM-sealed keys.** Ingest-node TPM sealing is Phase 1; agent-side TPM is Phase 2 unless a specific buyer requires it.
- **Hardware-backed auditor trust root** (auditor's smartcard as verifier trust anchor). Phase 2.
- **ClickHouse / columnar backing** for `audit_entries` at extreme scale. Postgres comfortable for Phase 1 and most of Phase 2.
- **Horizontal ingest sharding via per-tenant chains.** Phase 2 when multi-tenant deployments become real.
- **Log consistency witness gossiping** (CT-style cross-witnessing between Sentinel deployments). Neat, deferred.
- **Rust verifier port.** Phase 2 pending distribution-friction signals.

---

## References

- `docs/superpowers/specs/2026-04-21-sentinel-defense-pivot-design.md` — parent spec.
- RFC 6962 — Certificate Transparency (Merkle log hashing and proof algorithms).
- RFC 8785 — JCS (JSON Canonicalization Scheme).
- RFC 3161 — Time-Stamp Protocol.
- FIPS 186-5 — Digital Signature Standard (covers Ed25519, ECDSA).
- Google Trillian — architectural reference for the transparency-log pattern.
- Sigstore Rekor — applied Trillian transparency log for supply-chain artifacts; patterns consulted.
- `sdk/ATTRIBUTES.md` (current) — precursor to `sentinel/ATTRIBUTES.md`, which this spec depends on.

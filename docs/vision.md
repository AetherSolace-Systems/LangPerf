# LangPerf: Vision Document

**Domain:** langperf.com
**Tagline (working):** The agent improvement loop.
**Category:** Agent quality
**Culture/community wink:** agentmaxxing

> This document describes the full LangPerf product vision. The implementation
> in this repo is **v1** — a deliberately tight slice scoped to a single
> local-self-hosted user (see `ROADMAP.md` for what's explicitly deferred).

---

## One-line pitch

LangPerf is the collaboration surface where AI engineers and domain experts improve agents together — by looking at the same trajectory, flagging what went wrong, and turning that feedback into evals, training data, and better tools.

---

## The problem

Teams building vertical AI agents (coding, support, legal, sales, ops) hit a wall after prompt engineering. Their agents work most of the time, but the failure modes are subtle, domain-specific, and invisible to the engineers who built them.

The people who *can* see the failures — the domain subject-matter experts (SMEs) — don't have a tool built for them. Today, SME feedback lives in:

- Slack screenshots
- Ad-hoc Notion docs no one reads
- Thumbs-down events with no context
- Linear tickets disconnected from the actual trajectory

Meanwhile, engineers have observability tools (Langfuse, Arize, LangSmith) that were designed for debugging, not for collaboration with non-technical reviewers. The two groups look at different surfaces, speak different languages, and lose information at every handoff.

The result: agent quality plateaus. Teams can't systematically turn production failures into improvements.

---

## The insight

Fixing an agent isn't an observability problem. It isn't a pure RLHF tooling problem either. It's a **collaboration problem between the people who build the agent and the people who know what "right" looks like**. No one owns this surface.

The SME isn't just labeling data — they're generating engineering requirements. *"The agent keeps calling `search_orders` when it should call `search_invoices`"* is a tool design bug, surfaced by someone who'd never read the code. That's a new kind of feedback loop, and it deserves a product.

---

## The product

### Core: Agent Trajectory Studio

Every agent session has a UUID. The full trajectory renders as an interactive DAG (not a list, not a waterfall):

- User input → system prompt → thinking traces → tool calls (args + returns) → intermediate reasoning → retries → final output
- Zoom, pan, collapse branches
- Side-by-side diff of two runs (same input, different prompt/model versions)
- Click any node to see the exact context window at that moment
- Every node shows latency, token counts, cost, and parameters

### One screen, one shared reality

Engineers and SMEs look at the **same view**. When an SME says "step 4 is wrong," the engineer opens the link and sees exactly the same pixels. No mode switching, no hidden data, no "let me screenshot this for you." A unified surface is the entire point — splitting the UI would recreate the handoff problem we're trying to kill.

### Triage queue as the front door

Most tools drop you into an undifferentiated list of traces. LangPerf opens to a prioritized queue of runs that need attention:

- Thumbs-down from end users
- Explicit flags from SMEs or support
- Automated heuristics (latency spikes, tool errors, detected loops, apology-phrase detection, low-confidence outputs)
- Cluster view: "47 runs failed in the same way this week"

SMEs work the queue. Engineers get notified when SMEs flag patterns.

### Inline collaboration

- Comments thread on any node in the trajectory (think Figma-on-an-agent-step)
- SMEs can branch and rewrite: "here's what the agent should have done from step 4 onward" — generating paired preference data automatically
- Tag failure modes (wrong tool, bad args, hallucinated result, infinite loop, misunderstood intent)
- Mark resolved, link to fixes, @-mention teammates

### Dev + prod

- **In dev:** Replay trajectories against new prompts, new models, new tool definitions. "Would v2 have gotten this right?"
- **In prod:** Capture, annotate, cluster, export. Replay is read-only; the value is in turning real failures into structured feedback.

Same UUID schema spans both. Actions available differ by environment.

### The improvement loop (the real pitch)

```
Production failures
       ↓ (flagged)
   Triage queue
       ↓ (SME annotates)
  Structured feedback
       ↓ (exported)
 Eval sets + training data + engineering tickets
       ↓ (fed back)
  Better prompts, tools, routing, models
       ↓
Fewer production failures
```

LangPerf owns the capture-and-annotate middle. The value flows out to where work actually happens.

---

## Export surface

LangPerf is the system of record for agent behavior and the system of insight for the team — but **not** the system of action. We don't try to replace Notion, Linear, or GitHub. We feed them.

Exports include:

- **Markdown summaries** of flagged patterns → Notion/Confluence playbooks
- **JSONL trajectories with SME corrections** → fine-tuning pipelines (SFT, DPO, step-level reward)
- **Eval sets** derived from flagged clusters → CI/regression testing
- **Trace permalinks** → Slack, Linear, GitHub issues
- **CSV of tagged failure modes** → product analytics, roadmap planning

---

## Target customer

**First-wave ICP:** 10–50 person startups building a vertical AI agent (coding, support, legal, sales, ops, healthcare). They have:

- A working agent in production
- Prompt engineering has plateaued
- Real users flagging real failures
- Domain SMEs involved in quality (either in-house or contracted)
- Interest in fine-tuning but no good pipeline for training data

**Two personas inside the account:**

- **AI engineer / ML engineer:** Owns the agent code, prompts, tools, model choice. Buys the tool.
- **Domain SME / quality lead:** Owns "is this actually right?" Uses the tool most.

Both need to see the same page. This is non-negotiable.

---

## Positioning

**What we are:** An agent quality platform. A collaboration surface for improving agent behavior.

**What we are not:**

- Not observability (Langfuse, Arize, LangSmith, Helicone)
- Not an LLM gateway or router (OpenRouter, Martian)
- Not an eval harness alone (Promptfoo, Braintrust — though we generate eval sets)
- Not RLHF-as-a-service (Scale, Surge — we're the tool teams use themselves)
- Not a workflow/docs tool (Notion, Linear — we export to them)

**Competitive moat:** The unified collaboration surface. Engineer and SME literally look at the same screen, same trajectory, same pixels — with progressive disclosure handling the technical depth gap. Observability tools exclude SMEs by design; annotation tools exclude engineers by design. Nobody has built one surface for both.

---

## Open source + commercial split

**Open source:**

- SDK / tracer (framework-agnostic — OpenAI, Anthropic, LangChain, LlamaIndex, custom)
- Local viewer
- Self-hosted server
- Basic annotation and commenting
- Core export formats

**Commercial (hosted + enterprise):**

- Hosted cloud version with SSO, audit logs, data residency
- Team collaboration: annotator management, assign trajectories, inter-annotator agreement, rubrics
- Advanced triage (clustering, anomaly detection, automated heuristics library)
- Training data export pipelines with direct integrations (Together, Fireworks, OpenAI fine-tuning, HF TRL)
- Replay-against-new-prompt in dev
- Regression CI (run flagged clusters against every prompt change)

---

## Instrumentation architecture

**Decision: OTel-native from day one.** LangPerf ingestion speaks OpenTelemetry OTLP as the wire format, with a LangPerf SDK layered on top for developer experience.

### Tier 1: LangPerf SDK (Python, TypeScript)

The premium, batteries-included experience for the languages where most agent code lives. Built *on top of* the OpenTelemetry SDK — not parallel to it.

**LangPerf-native attributes** layered on top of OTel GenAI semconv (all prefixed `langperf.*`):

- `langperf.trajectory.id` — the top-level session UUID
- `langperf.trajectory.environment` — dev/staging/prod
- `langperf.node.kind` — richer than OTel's operation name (tool_call, llm_call, thinking, sub_agent, retry, human_correction)
- `langperf.feedback.*` — thumbs up/down, SME ratings, failure-mode tags
- `langperf.correction.*` — branched rewrites for preference-pair generation
- `langperf.replay.*` — markers for replay-in-dev support

### Tier 2: OpenTelemetry OTLP endpoint

`/v1/traces` accepts OTLP over HTTP (JSON and protobuf). Any OTel-compatible source works with zero LangPerf code.

### Tier 3: Framework integrations

Thin wrappers around existing OTel GenAI instrumentation libraries. Priority order:

1. OpenAI Python SDK + OpenAI Agents SDK
2. Anthropic Python SDK + Claude Agent SDK
3. LangChain / LangGraph
4. LlamaIndex / LlamaIndex Workflows
5. Vercel AI SDK (TypeScript)
6. CrewAI

---

## Naming conventions

- **LangPerf** — product name
- **Trajectory** — a single end-to-end agent session (UUID scoped)
- **Trace** — synonym for trajectory, closer to dev vocabulary
- **Node / step** — a single action inside a trajectory (tool call, LLM call, thinking block)
- **Triage queue** — the prioritized list of flagged runs
- **Annotation** — any SME or engineer input attached to a node or trajectory
- **Cluster** — a group of trajectories sharing a failure mode
- **Improvement loop** — the end-to-end cycle from failure capture to deployed fix

---

## What success looks like at full vision

- An AI engineer can drop our SDK into their agent in <10 minutes and see full trajectories
- A domain SME with no engineering background can open a flagged run, read the DAG as a narrative, leave a comment on a specific step, and mark a failure mode in under 3 minutes — without ever toggling into a different view
- A team can export a month of annotated failures as a JSONL fine-tuning dataset in one click
- Engineer and SME have a threaded conversation on the same trajectory without leaving the tool
- The team can show their CEO a chart of "failure modes this month" that actually reflects reality

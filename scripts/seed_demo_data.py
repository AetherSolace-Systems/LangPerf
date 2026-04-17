"""Seed LangPerf with varied, complex demo trajectories.

    pip install -e ./sdk
    python scripts/seed_demo_data.py

Generates ~7 trajectories with different shapes — multi-tool, multi-agent
supervisor, parallel calls, retries with errors, deep reasoning chains,
nested sub-agents — spread across the last 24 hours so the UI has realistic
variety to browse and filter.

No external LLM required. All spans are synthesized directly via OTel with
OpenInference-style attributes, so the UI renders them exactly like real
instrumented traces. Span start/end times are set explicitly via a
simulated clock, giving each node a realistic duration without actually
sleeping for seconds per call.
"""

from __future__ import annotations

import json
import random
import time
import uuid
from contextlib import contextmanager
from typing import Any, Iterator

import langperf
from opentelemetry import trace as trace_api
from opentelemetry.trace import Status, StatusCode, use_span

# --------------------------------------------------------------------------- #
# Simulated clock                                                              #
# --------------------------------------------------------------------------- #

_NS_PER_MS = 1_000_000

# Start cursor 24 hours ago, so trajectories spread across the last day.
_cursor_ns = int(time.time_ns()) - 24 * 60 * 60 * 1000 * _NS_PER_MS


def _advance_ms(ms: float) -> int:
    global _cursor_ns
    _cursor_ns += int(ms * _NS_PER_MS)
    return _cursor_ns


def _jump_between_trajectories() -> None:
    """Jump forward 3-120 minutes between trajectories for realistic spacing."""
    _advance_ms(random.uniform(3 * 60 * 1000, 120 * 60 * 1000))


# --------------------------------------------------------------------------- #
# Span primitives                                                              #
# --------------------------------------------------------------------------- #

_tracer = None
_current_traj_id: str | None = None
_current_traj_name: str | None = None


def _tracer_obj():
    global _tracer
    if _tracer is None:
        _tracer = trace_api.get_tracer("langperf.demo_seed")
    return _tracer


def _stamp_trajectory(span) -> None:
    if _current_traj_id:
        span.set_attribute("langperf.trajectory.id", _current_traj_id)
    if _current_traj_name:
        span.set_attribute("langperf.trajectory.name", _current_traj_name)


@contextmanager
def fake_trajectory(name: str, own_duration_ms: float = 5) -> Iterator[None]:
    """Open a trajectory root span with an explicit time range."""
    global _current_traj_id, _current_traj_name
    _jump_between_trajectories()
    _current_traj_id = str(uuid.uuid4())
    _current_traj_name = name
    tracer = _tracer_obj()
    start = _cursor_ns
    span = tracer.start_span(name, start_time=start)
    span.set_attribute("langperf.node.kind", "trajectory")
    _stamp_trajectory(span)
    try:
        with use_span(span, end_on_exit=False):
            yield
    finally:
        _advance_ms(own_duration_ms)
        span.end(end_time=_cursor_ns)
        _current_traj_id = None
        _current_traj_name = None


@contextmanager
def fake_agent(
    name: str, description: str = "", own_duration_ms: float = 3
) -> Iterator[None]:
    """Open a nested agent scope. Children nest under it."""
    tracer = _tracer_obj()
    start = _cursor_ns
    span = tracer.start_span(name, start_time=start)
    span.set_attribute("langperf.node.kind", "agent")
    span.set_attribute("langperf.node.name", name)
    if description:
        span.set_attribute("langperf.note", description)
    _stamp_trajectory(span)
    try:
        with use_span(span, end_on_exit=False):
            yield
    finally:
        _advance_ms(own_duration_ms)
        span.end(end_time=_cursor_ns)


def fake_llm(
    *,
    name: str = "ChatCompletion",
    system: str,
    user: str,
    response: str = "",
    tool_calls: list[dict] | None = None,
    model: str = "gpt-4o",
    prompt_tok: int = 0,
    completion_tok: int = 0,
    duration_ms: float = 150,
    status: str = "OK",
) -> None:
    """Synthesize an OpenInference-style LLM span with explicit time range."""
    tracer = _tracer_obj()
    start = _cursor_ns
    span = tracer.start_span(name, start_time=start)
    try:
        _stamp_trajectory(span)
        span.set_attribute("openinference.span.kind", "LLM")
        span.set_attribute("llm.system", "openai")
        span.set_attribute("llm.model_name", model)
        span.set_attribute(
            "llm.invocation_parameters",
            json.dumps({"model": model, "temperature": 0.7}),
        )

        messages: list[dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})

        for i, m in enumerate(messages):
            span.set_attribute(f"llm.input_messages.{i}.message.role", m["role"])
            span.set_attribute(
                f"llm.input_messages.{i}.message.content", m["content"]
            )

        span.set_attribute("llm.output_messages.0.message.role", "assistant")
        if response:
            span.set_attribute("llm.output_messages.0.message.content", response)
        if tool_calls:
            for j, tc in enumerate(tool_calls):
                base = f"llm.output_messages.0.message.tool_calls.{j}.tool_call"
                span.set_attribute(f"{base}.function.name", tc["name"])
                span.set_attribute(
                    f"{base}.function.arguments", json.dumps(tc.get("args", {}))
                )
                if "id" in tc:
                    span.set_attribute(f"{base}.id", tc["id"])

        if prompt_tok:
            span.set_attribute("llm.token_count.prompt", prompt_tok)
        if completion_tok:
            span.set_attribute("llm.token_count.completion", completion_tok)
        if prompt_tok and completion_tok:
            span.set_attribute("llm.token_count.total", prompt_tok + completion_tok)

        span.set_attribute(
            "input.value", json.dumps({"messages": messages, "model": model})
        )
        span.set_attribute("input.mime_type", "application/json")

        output_content: dict[str, Any] = {"role": "assistant", "content": response or ""}
        if tool_calls:
            output_content["tool_calls"] = [
                {
                    "id": tc.get("id", f"call_{j}"),
                    "function": {
                        "name": tc["name"],
                        "arguments": json.dumps(tc.get("args", {})),
                    },
                }
                for j, tc in enumerate(tool_calls)
            ]
        span.set_attribute(
            "output.value",
            json.dumps(
                {
                    "choices": [{"message": output_content}],
                    "model": model,
                    "usage": {
                        "prompt_tokens": prompt_tok,
                        "completion_tokens": completion_tok,
                        "total_tokens": prompt_tok + completion_tok,
                    },
                }
            ),
        )
        span.set_attribute("output.mime_type", "application/json")

        if status == "ERROR":
            span.set_status(Status(StatusCode.ERROR, "demo error"))
    finally:
        _advance_ms(duration_ms)
        span.end(end_time=_cursor_ns)


def fake_tool(
    *,
    name: str,
    args: Any,
    result: Any = None,
    description: str = "",
    duration_ms: float = 80,
    status: str = "OK",
) -> None:
    """Synthesize a tool_call span."""
    tracer = _tracer_obj()
    start = _cursor_ns
    span = tracer.start_span(name, start_time=start)
    try:
        _stamp_trajectory(span)
        span.set_attribute("openinference.span.kind", "TOOL")
        span.set_attribute("langperf.node.kind", "tool_call")
        span.set_attribute("langperf.node.name", name)
        span.set_attribute("tool.name", name)
        if description:
            span.set_attribute("tool.description", description)
        args_str = args if isinstance(args, str) else json.dumps(args)
        span.set_attribute("input.value", args_str)
        span.set_attribute("input.mime_type", "application/json")
        if result is not None:
            result_str = result if isinstance(result, str) else json.dumps(result)
            span.set_attribute("output.value", result_str)
            span.set_attribute("output.mime_type", "application/json")
        if status == "ERROR":
            span.set_status(Status(StatusCode.ERROR, "demo error"))
    finally:
        _advance_ms(duration_ms)
        span.end(end_time=_cursor_ns)


def fake_reasoning(*, name: str, thought: str = "", duration_ms: float = 30) -> None:
    tracer = _tracer_obj()
    start = _cursor_ns
    span = tracer.start_span(name, start_time=start)
    try:
        _stamp_trajectory(span)
        span.set_attribute("langperf.node.kind", "reasoning")
        span.set_attribute("langperf.node.name", name)
        if thought:
            span.set_attribute("langperf.note", thought)
    finally:
        _advance_ms(duration_ms)
        span.end(end_time=_cursor_ns)


# --------------------------------------------------------------------------- #
# Trajectories                                                                 #
# --------------------------------------------------------------------------- #


def traj_simple_greeting() -> None:
    with fake_trajectory("quick greeting"):
        fake_llm(
            system="You are a concise friendly assistant.",
            user="Hi!",
            response="Hi there — how can I help today?",
            model="gpt-4o-mini",
            prompt_tok=15,
            completion_tok=10,
            duration_ms=42,
        )


def traj_multi_tool_email() -> None:
    with fake_trajectory("draft and send follow-up email"):
        fake_llm(
            name="plan",
            system="You are an executive assistant. Use tools for contacts and email.",
            user="Draft and send a follow-up email to sarah@acme.com about our Q3 contract renewal.",
            response="I'll look up Sarah's record, draft the email, then send it.",
            model="gpt-4o",
            prompt_tok=140,
            completion_tok=35,
            duration_ms=320,
            tool_calls=[
                {"name": "search_contacts", "args": {"email": "sarah@acme.com"}, "id": "c1"}
            ],
        )
        fake_tool(
            name="search_contacts",
            args={"email": "sarah@acme.com"},
            result={
                "name": "Sarah Reyes",
                "company": "Acme",
                "title": "Procurement Lead",
                "last_contact": "2026-03-22",
            },
            duration_ms=85,
        )
        fake_llm(
            name="draft_email",
            system="Draft professional emails. Output: subject + body.",
            user="Follow up with Sarah Reyes (Procurement Lead, Acme) about Q3 contract renewal.",
            response=(
                "Subject: Q3 Contract Renewal — next steps\n\n"
                "Hi Sarah,\n\n"
                "Hope you're doing well! I wanted to follow up on the Q3 contract "
                "renewal we discussed in March. Let me know what timing works for "
                "a quick review call this week.\n\n"
                "Best,\nAlex"
            ),
            model="gpt-4o",
            prompt_tok=220,
            completion_tok=95,
            duration_ms=680,
            tool_calls=[
                {
                    "name": "send_email",
                    "args": {
                        "to": "sarah@acme.com",
                        "subject": "Q3 Contract Renewal — next steps",
                        "body": "<drafted body>",
                    },
                    "id": "c2",
                }
            ],
        )
        fake_tool(
            name="send_email",
            args={
                "to": "sarah@acme.com",
                "subject": "Q3 Contract Renewal — next steps",
            },
            result={
                "status": "sent",
                "message_id": "msg_8f2a1c",
                "sent_at": "2026-04-17T10:14:22Z",
            },
            duration_ms=135,
        )
        fake_llm(
            name="confirm",
            system="Confirm actions crisply.",
            user="I sent the email.",
            response="Done. Email sent to Sarah (message id msg_8f2a1c). I'll remind you if she hasn't replied by Friday.",
            model="gpt-4o-mini",
            prompt_tok=75,
            completion_tok=28,
            duration_ms=110,
        )


def traj_multi_agent_pricing() -> None:
    with fake_trajectory("research: competitive pricing analysis"):
        fake_llm(
            name="supervisor.plan",
            system="You are a research supervisor. Break work into sub-agent tasks.",
            user="Research competitive pricing for our SaaS product.",
            response=(
                "Plan: (1) market_research — look up public pricing for Notion, Linear, Asana. "
                "(2) customer_research — query our WTP survey data. "
                "(3) synthesize findings into a pricing recommendation."
            ),
            model="claude-sonnet-4-6",
            prompt_tok=260,
            completion_tok=75,
            duration_ms=470,
        )

        with fake_agent("market_research_agent", "gets competitor prices via web search"):
            fake_llm(
                name="market.plan",
                system="You research competitor pricing.",
                user="Gather public pricing for Notion, Linear, Asana.",
                response="Querying each company's pricing page.",
                model="gpt-4o",
                prompt_tok=160,
                completion_tok=25,
                duration_ms=180,
                tool_calls=[
                    {"name": "web_search", "args": {"q": "Notion pricing 2026"}, "id": "m1"},
                    {"name": "web_search", "args": {"q": "Linear pricing"}, "id": "m2"},
                    {"name": "web_search", "args": {"q": "Asana pricing"}, "id": "m3"},
                ],
            )
            fake_tool(
                name="web_search",
                args={"q": "Notion pricing 2026"},
                result={
                    "results": [
                        {
                            "url": "https://notion.so/pricing",
                            "snippet": "Free, Plus $8/user/mo, Business $15, Enterprise contact sales",
                        }
                    ]
                },
                duration_ms=420,
            )
            fake_tool(
                name="web_search",
                args={"q": "Linear pricing"},
                result={
                    "results": [
                        {
                            "url": "https://linear.app/pricing",
                            "snippet": "Free (up to 250 issues), Standard $10/user/mo, Plus $14/user/mo",
                        }
                    ]
                },
                duration_ms=380,
            )
            fake_tool(
                name="web_search",
                args={"q": "Asana pricing"},
                result={
                    "results": [
                        {
                            "url": "https://asana.com/pricing",
                            "snippet": "Free, Starter $10.99, Advanced $24.99, Enterprise custom",
                        }
                    ]
                },
                duration_ms=510,
            )
            fake_llm(
                name="market.summarize",
                system="Summarize pricing tiers across competitors.",
                user="Compile pricing into a comparable table.",
                response=(
                    "Notion: $8-15/user/mo (Free → Business)\n"
                    "Linear: $10-14/user/mo\n"
                    "Asana: $11-25/user/mo\n\n"
                    "Median mid-tier: ~$14/user/mo."
                ),
                model="gpt-4o",
                prompt_tok=460,
                completion_tok=58,
                duration_ms=420,
            )

        with fake_agent("customer_research_agent", "queries our survey DB for WTP data"):
            fake_llm(
                name="customer.plan",
                system="You query customer research databases.",
                user="Look up our user survey on willingness-to-pay.",
                response="Querying the survey database for max-price responses.",
                model="gpt-4o-mini",
                prompt_tok=120,
                completion_tok=20,
                duration_ms=140,
                tool_calls=[
                    {
                        "name": "query_db",
                        "args": {
                            "query": "SELECT avg(max_price), percentile_cont(0.5), count(*) FROM wtp_survey WHERE asked_at > '2026-01-01'"
                        },
                    }
                ],
            )
            fake_tool(
                name="query_db",
                args={
                    "query": "SELECT avg(max_price), percentile_cont(0.5), count(*) FROM wtp_survey WHERE asked_at > '2026-01-01'"
                },
                result={"avg_max_price": 18.50, "median": 17.00, "n": 147},
                duration_ms=220,
            )
            fake_llm(
                name="customer.summarize",
                system="Summarize survey results.",
                user="Give me the key number.",
                response="Across 147 respondents (Jan–Apr 2026): mean WTP $18.50/user/mo, median $17.00.",
                model="gpt-4o-mini",
                prompt_tok=90,
                completion_tok=28,
                duration_ms=105,
            )

        fake_llm(
            name="supervisor.synthesize",
            system="Synthesize into pricing recommendation.",
            user="Given competitor range $8-25 (median $14) and WTP median $17, recommend tiers.",
            response=(
                "Recommend three tiers:\n"
                "  Starter  $12/user/mo  — undercut median; target new teams\n"
                "  Pro     $18/user/mo  — at WTP median; target growing teams\n"
                "  Business $26/user/mo — above competitors; target companies with compliance needs\n\n"
                "Rationale: Pro captures mid-market exactly at their stated WTP; Starter creates a soft entry point below the field; Business differentiates on features we already have (SSO, audit log)."
            ),
            model="claude-opus-4-7",
            prompt_tok=640,
            completion_tok=165,
            duration_ms=1840,
        )


def traj_retry_with_error() -> None:
    with fake_trajectory("slack notify (with retry after rate-limit)"):
        fake_llm(
            name="plan",
            system="You are an ops assistant. Send Slack messages when asked.",
            user="Notify #ops that the deploy to prod-us-east-1 just completed.",
            response="Posting to #ops.",
            model="gpt-4o-mini",
            prompt_tok=55,
            completion_tok=10,
            duration_ms=75,
            tool_calls=[
                {
                    "name": "slack_post",
                    "args": {
                        "channel": "#ops",
                        "text": "deploy to prod-us-east-1 complete",
                    },
                    "id": "s1",
                }
            ],
        )
        fake_tool(
            name="slack_post",
            args={"channel": "#ops", "text": "deploy to prod-us-east-1 complete"},
            result={"error": "rate_limited", "retry_after_ms": 800},
            duration_ms=110,
            status="ERROR",
        )
        fake_reasoning(
            name="retry_decision",
            thought="Rate-limited. Backoff 800ms and retry.",
            duration_ms=820,
        )
        fake_tool(
            name="slack_post",
            args={"channel": "#ops", "text": "deploy to prod-us-east-1 complete"},
            result={"ok": True, "channel": "C0123", "ts": "1713370200.012345"},
            duration_ms=98,
        )
        fake_llm(
            name="confirm",
            system="Confirm actions.",
            user="Did it work?",
            response="Yes — posted on retry. Message ts 1713370200.012345.",
            model="gpt-4o-mini",
            prompt_tok=62,
            completion_tok=22,
            duration_ms=85,
        )


def traj_parallel_enrich() -> None:
    with fake_trajectory("enrich customer record (parallel fetches)"):
        fake_llm(
            name="plan",
            system="You enrich customer records from multiple data sources.",
            user="Enrich customer_id=c_001 with data from Stripe, Segment, and Salesforce.",
            response="Fetching all three in parallel.",
            model="gpt-4o",
            prompt_tok=140,
            completion_tok=20,
            duration_ms=260,
            tool_calls=[
                {"name": "stripe_get", "args": {"customer_id": "c_001"}, "id": "p1"},
                {"name": "segment_get", "args": {"customer_id": "c_001"}, "id": "p2"},
                {"name": "salesforce_get", "args": {"customer_id": "c_001"}, "id": "p3"},
            ],
        )
        fake_tool(
            name="stripe_get",
            args={"customer_id": "c_001"},
            result={"mrr": 2400, "plan": "business", "subscription_id": "sub_4J2"},
            duration_ms=230,
        )
        fake_tool(
            name="segment_get",
            args={"customer_id": "c_001"},
            result={
                "events_last_30d": 1582,
                "last_seen": "2026-04-15T22:41:00Z",
                "top_event": "agent_call",
            },
            duration_ms=180,
        )
        fake_tool(
            name="salesforce_get",
            args={"customer_id": "c_001"},
            result={
                "owner": "Ayesha Khan",
                "stage": "expansion",
                "close_date_hint": "2026-06-30",
            },
            duration_ms=310,
        )
        fake_llm(
            name="merge",
            system="Merge multi-source customer data into a unified view.",
            user="Three payloads: stripe, segment, salesforce. Produce one record.",
            response=json.dumps(
                {
                    "id": "c_001",
                    "plan": "business",
                    "mrr": 2400,
                    "events_last_30d": 1582,
                    "last_seen": "2026-04-15T22:41:00Z",
                    "owner": "Ayesha Khan",
                    "stage": "expansion",
                    "summary": "High-engagement expansion account on business plan; owned by Ayesha Khan.",
                },
                indent=2,
            ),
            model="gpt-4o",
            prompt_tok=340,
            completion_tok=80,
            duration_ms=430,
        )


def traj_deep_reasoning() -> None:
    with fake_trajectory("plan: postgres → cockroachdb migration"):
        fake_llm(
            name="initial_plan",
            system="You are a senior database engineer.",
            user="Create a migration plan from Postgres 16 to CockroachDB for our production order-service.",
            response=(
                "I'll break this into seven phases: schema survey, incompatibility scan, "
                "schema rewrite, dual-write setup, backfill, cutover, validation."
            ),
            model="claude-opus-4-7",
            prompt_tok=320,
            completion_tok=65,
            duration_ms=720,
        )
        phases = [
            ("survey_schema", "Enumerate tables, indexes, constraints, triggers, sequences, custom types."),
            ("incompatibility_scan", "Flag: `serial` → `unique_rowid()`, JSONB operators, triggers, stored procs, specific collations."),
            ("schema_rewrite", "Produce CockroachDB-compatible DDL. Keep primary keys stable. Replace sequences with `unique_rowid()`."),
            ("dual_write_plan", "Set up logical replication via a CDC pipeline to shadow-write to CRDB; compare row-by-row."),
            ("backfill_historicals", "Snapshot + stream strategy. Estimated 4-6 hour backfill window for ~380M rows."),
            ("cutover_plan", "Drain order-service requests via load balancer. Pause writes <60s. Verify tail of replica. Flip DSN. Resume."),
            ("validation_plan", "Shadow-read both DBs for 24h, compare. Spot-check 100 random orders for field-level parity. Replay any divergent txns."),
        ]
        for phase_name, prompt in phases:
            fake_reasoning(
                name=f"think.{phase_name}",
                thought=prompt,
                duration_ms=random.uniform(20, 60),
            )
            fake_llm(
                name=f"phase.{phase_name}",
                system="You design database migration phases in detail.",
                user=prompt,
                response=(
                    f"[phase: {phase_name}]\n\n"
                    "1. Actions: …\n2. Risks: …\n3. Rollback: …\n"
                    f"4. Est. duration: {random.choice(['30min', '2h', '4h', '8h', '1 day'])}."
                ),
                model="claude-sonnet-4-6",
                prompt_tok=random.randint(260, 420),
                completion_tok=random.randint(80, 180),
                duration_ms=random.uniform(380, 860),
            )
        fake_llm(
            name="synthesize_risks",
            system="Identify top risks across phases.",
            user="What's the highest-risk phase, and what's the mitigation?",
            response=(
                "Highest risk: cutover. Mitigation: do two dry-run cutovers in staging against "
                "full-size data snapshots; keep Postgres as read-only standby for 48h after "
                "cutover for fast rollback."
            ),
            model="claude-opus-4-7",
            prompt_tok=540,
            completion_tok=95,
            duration_ms=980,
        )


def traj_nested_subagents() -> None:
    with fake_trajectory("triage + resolve support ticket"):
        with fake_agent("ticket_triage_agent", "classifies ticket and dispatches to specialist"):
            fake_llm(
                name="triage.classify",
                system="Classify tickets into categories with priority.",
                user="Ticket from customer c_042: 'My invoice this month shows $1200 but my contract says $1000. Why?'",
                response="Category: billing. Priority: medium. Route: billing_specialist.",
                model="gpt-4o-mini",
                prompt_tok=180,
                completion_tok=18,
                duration_ms=160,
            )
            with fake_agent("billing_specialist", "resolves billing discrepancies"):
                fake_llm(
                    name="billing.investigate",
                    system="Investigate invoice discrepancies.",
                    user="Customer c_042: invoice $1200, contract $1000. Explain the $200.",
                    response="I'll pull the invoice then cross-check against the contract.",
                    model="gpt-4o",
                    prompt_tok=220,
                    completion_tok=24,
                    duration_ms=280,
                    tool_calls=[
                        {
                            "name": "get_invoice",
                            "args": {"customer_id": "c_042", "period": "current"},
                            "id": "b1",
                        }
                    ],
                )
                fake_tool(
                    name="get_invoice",
                    args={"customer_id": "c_042", "period": "current"},
                    result={
                        "invoice_id": "inv_8421",
                        "total": 1200,
                        "line_items": [
                            {"description": "Pro plan base", "amount": 1000},
                            {"description": "Storage add-on (100GB)", "amount": 200},
                        ],
                    },
                    duration_ms=195,
                )
                with fake_agent("contract_lookup_agent", "pulls and parses contracts"):
                    fake_llm(
                        name="contract.plan",
                        system="Pull contract for a customer.",
                        user="Get contract for c_042 including addons.",
                        response="Querying contract DB.",
                        model="gpt-4o-mini",
                        prompt_tok=80,
                        completion_tok=10,
                        duration_ms=90,
                        tool_calls=[{"name": "get_contract", "args": {"customer_id": "c_042"}}],
                    )
                    fake_tool(
                        name="get_contract",
                        args={"customer_id": "c_042"},
                        result={
                            "contract_id": "k_3391",
                            "monthly_base": 1000,
                            "addons": [
                                {
                                    "name": "storage_100gb",
                                    "monthly_cost": 200,
                                    "added_at": "2026-03-15",
                                }
                            ],
                            "discount": 0.0,
                        },
                        duration_ms=260,
                    )
                    fake_llm(
                        name="contract.summarize",
                        system="Summarize a contract.",
                        user="Summarize c_042's contract state.",
                        response="c_042: $1000/mo base, plus one addon (storage_100gb @ $200/mo, added 2026-03-15). Total expected: $1200/mo.",
                        model="gpt-4o-mini",
                        prompt_tok=180,
                        completion_tok=40,
                        duration_ms=220,
                    )
                fake_llm(
                    name="billing.diagnose",
                    system="Diagnose the mismatch using invoice and contract.",
                    user="Invoice $1200, contract $1000 base + $200 addon = $1200. Verdict?",
                    response="Invoice is correct. The $200 diff is the storage_100gb addon added on 2026-03-15. No discrepancy.",
                    model="gpt-4o",
                    prompt_tok=380,
                    completion_tok=52,
                    duration_ms=420,
                )
            fake_llm(
                name="triage.respond",
                system="Draft a friendly customer response.",
                user="Explain the $200 addon charge to c_042.",
                response=(
                    "Hi there — thanks for flagging this! Your invoice is correct. "
                    "The extra $200 is for the 100GB storage add-on that was added to your "
                    "plan on March 15. Here's the breakdown:\n\n"
                    "  • Pro plan base: $1,000/mo\n"
                    "  • Storage add-on (100GB): $200/mo\n"
                    "  • Total: $1,200/mo\n\n"
                    "Let me know if you'd like to adjust the storage allocation or if I can "
                    "help with anything else."
                ),
                model="gpt-4o",
                prompt_tok=260,
                completion_tok=120,
                duration_ms=680,
            )


# --------------------------------------------------------------------------- #
# Main                                                                         #
# --------------------------------------------------------------------------- #


def main() -> int:
    langperf.init(service_name="langperf-demo-seed", environment="dev")

    trajectories = [
        ("quick greeting", traj_simple_greeting),
        ("draft and send follow-up email", traj_multi_tool_email),
        ("multi-agent: competitive pricing research", traj_multi_agent_pricing),
        ("slack retry after rate-limit", traj_retry_with_error),
        ("parallel customer enrichment", traj_parallel_enrich),
        ("deep reasoning: postgres → cockroach", traj_deep_reasoning),
        ("nested sub-agents: support triage", traj_nested_subagents),
    ]

    print("Seeding demo trajectories…")
    for label, fn in trajectories:
        fn()
        print(f"  ✓ {label}")

    langperf.flush()
    print("\nDone. Open http://localhost:3030 to browse.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

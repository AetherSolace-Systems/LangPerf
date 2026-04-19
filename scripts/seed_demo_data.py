"""Seed LangPerf with varied, complex demo trajectories.

    pip install -e ./sdk
    python scripts/seed_demo_data.py

Generates ~8 trajectories with different shapes — multi-tool, multi-agent
supervisor, parallel calls, retries with errors, deep reasoning chains,
nested sub-agents, parallel sub-agent fan-out — spread across the last 24
hours so the UI has realistic variety to browse and filter.

No external LLM required. All spans are synthesized via `scripts.demo_tracer`,
which emits OpenInference-shaped spans with explicit start/end times so the
UI renders them exactly like real instrumented traces, without actually
sleeping for seconds per call.
"""

from __future__ import annotations

import json
import random

import langperf

# scripts/ is not a package; when `seed_demo_data.py` is run directly Python
# adds this directory to sys.path so the sibling module import just works.
from demo_tracer import (
    fake_agent,
    fake_llm,
    fake_reasoning,
    fake_tool,
    fake_trajectory,
    parallel_branches,
)


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


def traj_parallel_research() -> None:
    """Supervisor launches 3 sub-agents in parallel, waits for all, synthesizes.

    The three sub-agents finish at very different times (1.5s, 2s, 3.5s) so
    their overlap pattern is visible on the timeline. On the graph, all three
    agents appear as dispatched by the supervisor with aggregated edges.
    """
    def climate_agent() -> None:
        with fake_agent("climate_data_agent", "fetches and summarizes climate data"):
            fake_llm(
                name="climate.plan",
                system="You research climate data.",
                user="Gather NOAA temperature anomalies and IPCC projections for 2020-2025.",
                response="Fetching NOAA then IPCC.",
                model="gpt-4o",
                prompt_tok=180,
                completion_tok=20,
                duration_ms=220,
                tool_calls=[
                    {"name": "fetch_noaa_data", "args": {"years": [2020, 2025]}, "id": "c1"},
                    {"name": "fetch_ipcc_report", "args": {"report": "AR6 WG1"}, "id": "c2"},
                ],
            )
            fake_tool(
                name="fetch_noaa_data",
                args={"years": [2020, 2025]},
                result={
                    "anomaly_c": [1.14, 1.22, 1.31, 1.45, 1.48, 1.52],
                    "unit": "°C above 1850-1900 baseline",
                },
                duration_ms=640,
            )
            fake_tool(
                name="fetch_ipcc_report",
                args={"report": "AR6 WG1"},
                result={
                    "sections": ["SPM", "Ch3", "Ch4", "Ch7"],
                    "key_projections": "1.5°C warming likely by early 2030s under all scenarios.",
                },
                duration_ms=810,
            )
            fake_llm(
                name="climate.summarize",
                system="Summarize climate findings.",
                user="Given the NOAA + IPCC data, summarize trend.",
                response=(
                    "Global temperature anomaly has risen steadily from 1.14°C (2020) to "
                    "1.52°C (2025) above pre-industrial baseline. IPCC AR6 projects 1.5°C "
                    "threshold likely crossed in early 2030s across all emissions scenarios."
                ),
                model="gpt-4o",
                prompt_tok=360,
                completion_tok=85,
                duration_ms=420,
            )

    def economic_agent() -> None:
        with fake_agent("economic_analysis_agent", "queries economic impact data"):
            fake_llm(
                name="economic.plan",
                system="You analyze economic impact of climate change.",
                user="Look up World Bank estimates for climate GDP impact.",
                response="Querying World Bank climate indicators.",
                model="claude-sonnet-4-6",
                prompt_tok=200,
                completion_tok=22,
                duration_ms=310,
                tool_calls=[
                    {
                        "name": "query_world_bank",
                        "args": {"indicator": "climate_gdp_impact", "region": "global"},
                        "id": "e1",
                    }
                ],
            )
            fake_tool(
                name="query_world_bank",
                args={"indicator": "climate_gdp_impact", "region": "global"},
                result={
                    "baseline_gdp_2050": 230e12,
                    "climate_drag_pct_low": 4.2,
                    "climate_drag_pct_high": 18.0,
                    "note": "Range depends on warming trajectory (1.5°C vs 3°C scenarios).",
                },
                duration_ms=520,
            )
            fake_llm(
                name="economic.analyze",
                system="Analyze economic impact.",
                user="Translate World Bank figures into a narrative.",
                response=(
                    "At a 1.5°C trajectory, global GDP in 2050 drags 4.2% below baseline "
                    "(≈ $9.7T). At 3°C, drag widens to 18% (≈ $41.4T). Largest losses in "
                    "agriculture and low-lying coastal regions."
                ),
                model="claude-sonnet-4-6",
                prompt_tok=410,
                completion_tok=95,
                duration_ms=680,
            )

    def social_agent() -> None:
        with fake_agent("social_impact_agent", "analyzes displacement + migration data"):
            fake_llm(
                name="social.plan",
                system="You analyze climate's social impact.",
                user="Gather news + survey data on climate migration.",
                response="Scraping news + pulling UNHCR survey data.",
                model="gpt-4o-mini",
                prompt_tok=170,
                completion_tok=18,
                duration_ms=195,
                tool_calls=[
                    {
                        "name": "scrape_news",
                        "args": {"query": "climate migration 2024-2025", "n": 50},
                        "id": "s1",
                    },
                    {
                        "name": "fetch_survey_data",
                        "args": {"source": "UNHCR", "topic": "climate_displacement"},
                        "id": "s2",
                    },
                ],
            )
            fake_tool(
                name="scrape_news",
                args={"query": "climate migration 2024-2025", "n": 50},
                result={
                    "articles": 47,
                    "key_themes": [
                        "Sahel food-security displacement",
                        "Bangladesh delta flooding",
                        "US West fire migration",
                        "Mediterranean crossings up 23%",
                    ],
                },
                duration_ms=1040,
            )
            fake_tool(
                name="fetch_survey_data",
                args={"source": "UNHCR", "topic": "climate_displacement"},
                result={
                    "displaced_2024": 32_600_000,
                    "yoy_change_pct": 18.2,
                    "top_regions": ["Sub-Saharan Africa", "South Asia", "Central America"],
                },
                duration_ms=820,
            )
            fake_llm(
                name="social.synthesize",
                system="Synthesize social impact findings.",
                user="Combine news themes + UNHCR data into a readable synthesis.",
                response=(
                    "32.6M people were climate-displaced in 2024 (+18.2% YoY). Hotspots "
                    "cluster in Sub-Saharan Africa (food-security), South Asia (Bangladesh "
                    "delta flooding), and Central America (drought-driven migration). News "
                    "coverage reflects these themes but over-indexes on Mediterranean "
                    "crossings relative to total displacement."
                ),
                model="gpt-4o",
                prompt_tok=520,
                completion_tok=145,
                duration_ms=1230,
            )
            fake_llm(
                name="social.cross_reference",
                system="Cross-reference against climate projections.",
                user="Does this trend correlate with temperature anomalies?",
                response="Displacement curve tracks anomaly curve with ~2-year lag in affected regions.",
                model="gpt-4o",
                prompt_tok=320,
                completion_tok=42,
                duration_ms=310,
            )

    with fake_trajectory("parallel research: climate impact study"):
        fake_llm(
            name="supervisor.plan",
            system="You coordinate multi-domain research teams.",
            user="Produce a climate impact briefing covering: raw climate data, economic impact, and social/displacement impact. Launch specialist agents in parallel.",
            response=(
                "Dispatching three agents in parallel:\n"
                "  1. climate_data_agent  — NOAA + IPCC\n"
                "  2. economic_analysis_agent — World Bank GDP impact\n"
                "  3. social_impact_agent — UNHCR + news\n"
                "Will synthesize once all three report back."
            ),
            model="claude-opus-4-7",
            prompt_tok=320,
            completion_tok=85,
            duration_ms=510,
        )

        parallel_branches([climate_agent, economic_agent, social_agent])

        fake_reasoning(
            name="wait_for_all_agents",
            thought="All 3 sub-agents have reported back. Ready to synthesize.",
            duration_ms=8,
        )

        fake_llm(
            name="supervisor.synthesize",
            system="You synthesize multi-agent research into a single briefing.",
            user="Combine climate data, economic impact, and social impact into a 3-paragraph briefing.",
            response=(
                "**Climate trajectory.** Global temperature anomaly has risen from 1.14°C (2020) to 1.52°C (2025) above pre-industrial baseline. IPCC AR6 projects the 1.5°C threshold is likely crossed in the early 2030s across all emissions scenarios.\n\n"
                "**Economic impact.** At a 1.5°C trajectory, global 2050 GDP drags 4.2% below baseline (≈ $9.7T). At 3°C, drag widens to 18% (≈ $41.4T), concentrated in agriculture and low-lying coastal regions.\n\n"
                "**Social impact.** 32.6M people were climate-displaced in 2024 (+18.2% YoY), concentrated in Sub-Saharan Africa (food-security), South Asia (Bangladesh delta flooding), and Central America (drought-driven migration). Displacement tracks the temperature anomaly curve with roughly a two-year lag in affected regions.\n\n"
                "**Conclusion.** Warming, economic drag, and forced displacement are not independent trends — they correlate strongly and accelerate together. Mitigation spending that averts $1 of climate drag also averts meaningful displacement downstream."
            ),
            model="claude-opus-4-7",
            prompt_tok=920,
            completion_tok=280,
            duration_ms=1740,
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
    langperf.init(agent_name="langperf-demo-seed", environment="dev")

    trajectories = [
        ("quick greeting", traj_simple_greeting),
        ("draft and send follow-up email", traj_multi_tool_email),
        ("multi-agent: competitive pricing research", traj_multi_agent_pricing),
        ("slack retry after rate-limit", traj_retry_with_error),
        ("parallel customer enrichment", traj_parallel_enrich),
        ("deep reasoning: postgres → cockroach", traj_deep_reasoning),
        ("nested sub-agents: support triage", traj_nested_subagents),
        ("parallel sub-agents: climate impact study", traj_parallel_research),
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

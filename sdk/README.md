# `langperf` — Python SDK

Tracer + feedback primitives for agent trajectories. Drop into any Python
agent (OpenAI SDK, LM Studio, or any OpenAI-compatible endpoint) and your
agent runs show up in LangPerf's UI within a batch-export window.

**Status:** v0.2.0 — Python, OpenAI SDK. TS SDK and framework wrappers are
on the roadmap, not here yet.

---

## Install

```bash
pip install langperf   # coming soon; today: pip install -e ./sdk
```

## Setup

1. Register your agent in the LangPerf UI (Agents → + Add agent). You'll
   receive an API token — save it; it's shown once.
2. Set the token in your environment:

   ```bash
   export LANGPERF_API_TOKEN=lp_xxxxxxxx_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```

3. Initialize at program start:

   ```python
   import langperf

   langperf.init(
       agent_name="weather-bot",
       environment="prod",
       version="1.2.3",
       # api_token= and endpoint= default to env vars
   )
   ```

Everything flowing through the OpenAI Python SDK is captured automatically
after `init()` — messages, tool calls, token counts, timing, model name.

---

## Surface

| API | Purpose |
| --- | --- |
| `init(...)` | Configure the tracer + auto-install OpenAI instrumentation. Call once at startup. |
| `trajectory(name, *, user_id, session_id, metadata)` | Context manager scoping one agent run. Root span for the tree. |
| `node(*, kind, name, metadata)` | Span for a logical step inside a trajectory. Context manager or decorator. |
| `tool(name)` | Decorator sugar over `node(kind="tool")` with automatic args/result capture. |
| `mark(tag, note)` | Tag the active trajectory `good`/`bad`/`interesting`/`todo` and/or attach a note. Bridges to the UI filter column. |
| `metric(name, value)` | Stamp a scalar metric (`langperf.metric.<name>`) on the current span. |
| `set_user(user_id, email, display_name, session_id)` | Attach user attribution to the active trajectory after entering it. |
| `current_trajectory_id()` | Return the active trajectory UUID (for deep-linking back to `/t/<id>`). |
| `flush(timeout_millis)` | Force-flush pending spans. Call before process exit. |

All public names are re-exported from the top-level `langperf` package.

---

## Recipes

### Basic trajectory

```python
import langperf, openai

langperf.init(agent_name="weather-bot", environment="prod")
client = openai.OpenAI()

with langperf.trajectory("forecast query"):
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "weather in Austin?"}],
    )
```

### Nested nodes + decorator

```python
@langperf.node(kind="reasoning", name="plan")
def plan_next_step(state):
    ...

with langperf.trajectory("order lookup"):
    plan_next_step(state)
    with langperf.node(kind="retrieval", name="search"):
        docs = vector_store.query(...)
```

### Tools with auto-capture

```python
@langperf.tool
def search_orders(query: str, limit: int = 10) -> list[dict]:
    return db.search(query, limit)

@langperf.tool("weather-lookup")
async def fetch_weather(city: str) -> dict:
    return await http.get(f"/weather/{city}")
```

Args and return values are serialized to JSON (truncated at 16 KiB) and
land on the span as `langperf.tool.args` / `langperf.tool.result`. Raising
inside a tool records the exception and re-raises.

Opt out of capture when the payload is sensitive or huge:

```python
@langperf.tool("scan-customer", capture_args=False, capture_result=False)
def scan_customer(pii_blob): ...
```

### Tag from code (SDK-side triage signal)

```python
with langperf.trajectory("customer reply"):
    reply = agent.answer(question)
    if "I apologize" in reply:
        langperf.mark("bad", note="refusal response")
    elif agent.confidence < 0.6:
        langperf.mark("interesting", note=f"low confidence ({agent.confidence:.2f})")
```

These land in the UI's tag filter immediately — you don't have to open
LangPerf to triage.

### User + session attribution

```python
with langperf.trajectory(
    "checkout assistance",
    user_id=auth.current_user_id,
    session_id=request.session_id,
    metadata={"feature_flag": "nav_v2", "tenant": "acme"},
):
    ...
```

Or, when you learn the user mid-run:

```python
with langperf.trajectory("auth flow"):
    user = authenticate(request)
    langperf.set_user(user.id, email=user.email, display_name=user.name)
    run_agent_steps(...)
```

### Custom metrics

```python
with langperf.trajectory("classify"):
    with langperf.node(kind="llm", name="prediction"):
        prediction, confidence = model(payload)
        langperf.metric("confidence", confidence)
        langperf.metric("token_budget_used", used_tokens / budget)
```

Visible in the span detail panel; read by future triage heuristics.

### Deep-link from your own logs

```python
with langperf.trajectory("customer query"):
    try:
        agent.run(q)
    except Exception:
        sentry_sdk.set_tag("langperf_trajectory", langperf.current_trajectory_id())
        raise
```

### Flush before exit

```python
try:
    run_agent()
finally:
    langperf.flush()
```

The OTLP batch exporter flushes on a 5-second tick by default; call `flush()`
before the process exits (CLI scripts, short-lived Lambdas) to not lose
the tail.

---

## Async

Every context manager + decorator works inside `asyncio` — the SDK uses
`contextvars` under the hood so concurrent trajectories don't leak into
each other. Use the same API in async code:

```python
async def handle(request):
    with langperf.trajectory("request", user_id=request.user_id):
        return await agent.answer(request.text)
```

`@langperf.node` and `@langperf.tool` detect `async def` and wrap
accordingly.

---

## Environment variables

| Var | Effect | Default |
| --- | --- | --- |
| `LANGPERF_API_TOKEN` | **Required.** Per-agent bearer token minted in the UI. | — |
| `LANGPERF_ENDPOINT` | OTLP endpoint base URL. | `http://localhost:4318` |
| `LANGPERF_AGENT_NAME` | Agent name (falls back to `agent_name=` kwarg). | `langperf-agent` |
| `LANGPERF_ENVIRONMENT` | Maps to OTel `deployment.environment`. | unset |
| `LANGPERF_VERSION` | Sets `service.version`. | unset |
| `LANGPERF_SERVICE_NAME` | *(deprecated)* alias for `LANGPERF_AGENT_NAME`. | unset |

Tokens rotate via the UI; rotation invalidates the old one immediately.

---

## LM Studio / OpenAI-compatible endpoints

Works with any OpenAI-compatible API. Point the OpenAI client at your
local server; nothing else changes:

```python
import openai, langperf
langperf.init(agent_name="local-bot")
client = openai.OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")
client.chat.completions.create(model="gpt-oss-20b", messages=[...])
```

---

## Troubleshooting

**"LANGPERF_API_TOKEN is required"** — You called `init()` without setting
the env var or passing `api_token=`. Register an agent in the UI and copy
its token.

**Spans not showing up** — Default endpoint is `http://localhost:4318`; set
`LANGPERF_ENDPOINT` to your LangPerf deployment. Check the process hasn't
exited before the 5s batch flush; call `langperf.flush()` before exit.

**401 at ingest** — Token rotated or wrong agent; copy a fresh token from
the Agents page.

**Tool args/results look like JSON strings of reprs** — The value wasn't
JSON-serializable; the SDK falls back to `repr()` so you see *something*.
Make your tool's args/return value JSON-friendly, or pass
`capture_result=False` and emit a `metric()` / `metadata` instead.

---

## What goes into triage

SDK-emitted signals feed the triage queue in two ways:

1. **Heuristic inputs.** `langperf.metric(...)` values, exception events,
   and tool span statuses get read by the server-side heuristics engine
   (tool errors, latency outliers, apology phrases, loops,
   low-confidence). You don't interact with heuristics directly; they run
   automatically on every ingested trajectory.
2. **Manual signal.** `langperf.mark("bad")` / `mark("interesting")`
   populates `Trajectory.status_tag` so the UI's tag filters surface your
   explicit verdict from code.

See `ATTRIBUTES.md` for the full span-attribute contract.

---

## Versioning

Semver. Pre-1.0, minor bumps may change attribute keys — follow
`CHANGELOG.md`. Attribute keys are the stable wire-protocol contract
between SDK and backend; see `ATTRIBUTES.md`.

## Upgrade notes (0.1 → 0.2)

No breaking changes. New surface: `tool`, `mark`, `metric`, `set_user`,
`current_trajectory_id`, plus `user_id`/`session_id`/`metadata` kwargs on
`trajectory()` and `metadata` on `node()`.

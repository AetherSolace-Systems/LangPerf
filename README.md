# LangPerf

The agent improvement loop — local OSS self-hosted v1.

LangPerf captures agent trajectories (LLM calls, tool calls, sub-agent steps)
and gives you a local browsable UI for reviewing them, tagging runs, and
taking notes. Drop a one-line SDK `init()` into any Python agent using the
`openai` SDK — including local endpoints like LM Studio — and every call
becomes a named, navigable trajectory.

See [`docs/vision.md`](docs/vision.md) for the full product vision and
[`docs/ROADMAP.md`](docs/ROADMAP.md) for what's explicitly deferred to v2+.

## Quick start

### 1. Run the stack

```bash
docker compose up -d
```

Three services come up on your local machine:

| service          | port   | role                                     |
|------------------|--------|------------------------------------------|
| `langperf-api`   | `4318` | OTLP ingestion (`POST /v1/traces`) + UI API |
| `langperf-web`   | `3030` | Next.js UI                               |
| `postgres`       | —      | Storage (named volume `postgres_data`)   |

### 2. Instrument your agent

```bash
pip install -e ./sdk
```

```python
import langperf, openai

langperf.init(
    endpoint="http://localhost:4318",
    service_name="my-agent",
    environment="dev",
)

with langperf.trajectory(name="summarize inbox"):
    client = openai.OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")
    resp = client.chat.completions.create(
        model="local-model",
        messages=[{"role": "user", "content": "Hello"}],
    )

    @langperf.node(kind="tool_call", name="fetch_emails")
    def fetch_emails(): ...
    fetch_emails()

langperf.flush()
```

Open [http://localhost:3030](http://localhost:3030).

### 3. Try the demo

```bash
python examples/lm_studio_agent.py
```

A tiny multi-step agent that fires two LLM calls, a decorated tool call, and
an inline reasoning node — all inside one trajectory.

## SDK surface

Four public symbols.

| symbol                        | shape                                 | purpose                                                             |
|-------------------------------|---------------------------------------|---------------------------------------------------------------------|
| `langperf.init(...)`          | function, call once                   | Sets up the OTel exporter and auto-instruments the `openai` SDK     |
| `langperf.trajectory(name=?)` | context manager                       | Groups all spans inside the `with` block as one trajectory          |
| `langperf.node(kind=, name=?)`| context manager **or** decorator      | Wraps a block/function as its own tree node                         |
| `langperf.flush(timeout_ms=?)`| function                              | Forces pending spans through the batch exporter (use in scripts)    |

### Environment variable fallbacks

| variable                    | purpose                                               |
|-----------------------------|-------------------------------------------------------|
| `LANGPERF_ENDPOINT`         | OTLP endpoint (default `http://localhost:4318`)       |
| `LANGPERF_SERVICE_NAME`     | Service name shown in the UI                          |
| `LANGPERF_ENVIRONMENT`      | Maps to OTel `deployment.environment`                 |

## UI features (v1)

- Collapsible trajectory tree; click any row for kind-aware detail
- LLM view: roles, messages, tool calls, token counts, invocation params, raw response
- Tool view: args + result
- Generic JSON view for everything else
- Tag trajectories as `good` / `bad` / `interesting` / `todo`
- Free-form markdown notes on trajectories and on individual nodes
- Filter by tag, service, environment; full-text search across span content

## Directory layout

```
langperf/
├── docker-compose.yml
├── api/                  # FastAPI backend (OTLP ingest + UI API)
├── web/                  # Next.js UI
├── sdk/                  # `langperf` Python package
├── examples/             # Runnable demos
├── scripts/              # Dev helpers (e.g. smoke test)
└── docs/
    ├── vision.md         # Full product vision
    └── ROADMAP.md        # Explicit v2+ deferrals
```

## Instrumentation without the SDK

LangPerf's `/v1/traces` is standard OTLP/HTTP. Any OTel source works with zero
LangPerf-specific code — just point `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` at
`http://localhost:4318/v1/traces`. Without the SDK, trajectories group by OTel
`trace_id` (one trace = one trajectory). Use the SDK if you want multi-call
trajectories, custom node kinds, or named trajectories.

## License

See the repo root. (v1 is a solo dogfood build; licensing decisions still to come.)

# `langperf` — Python SDK

Tracer for agent trajectories. Designed to be dropped into any Python agent using
the `openai` SDK (or an OpenAI-compatible endpoint like LM Studio).

## Setup

1. Register your agent in the LangPerf UI (Agents → + Add agent). You'll
   receive an API token — save it; it's shown once.
2. Set the token in your environment:

   ```bash
   export LANGPERF_API_TOKEN=lp_xxxxxxxx_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```

3. Initialize:

   ```python
   import langperf
   langperf.init()  # reads LANGPERF_API_TOKEN from env
   # or
   langperf.init(api_token="lp_...")
   ```

## Usage

```python
import langperf, openai

langperf.init(endpoint="http://localhost:4318", service_name="my-agent")

client = openai.OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")
client.chat.completions.create(model="gpt-oss-20b", messages=[...])
```

Everything flowing through the `openai` SDK is captured automatically — messages,
tool calls, token counts, timing, model name.

## Environment variables

- `LANGPERF_API_TOKEN` — **required**; per-agent bearer token minted in the
  UI when you register the agent. Rotating the token in the UI invalidates
  the old one immediately.
- `LANGPERF_ENDPOINT` — OTLP endpoint base URL (default `http://localhost:4318`)
- `LANGPERF_SERVICE_NAME` — service name shown in the UI
- `LANGPERF_ENVIRONMENT` — maps to OTel `deployment.environment`

## Upgrade notes

Older versions of the SDK auto-detected agents by signature with no auth.
Starting with per-agent tokens, OTLP ingest requires `Authorization: Bearer
<token>` — requests without a valid token are rejected with 401. For
pre-existing auto-detected agents, click "Issue token" on the row in the
Agents table to mint a token; historical data is preserved.

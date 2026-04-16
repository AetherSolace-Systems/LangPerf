# `langperf` — Python SDK

Tracer for agent trajectories. Designed to be dropped into any Python agent using
the `openai` SDK (or an OpenAI-compatible endpoint like LM Studio).

```python
import langperf, openai

langperf.init(endpoint="http://localhost:4318", service_name="my-agent")

client = openai.OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")
client.chat.completions.create(model="gpt-oss-20b", messages=[...])
```

Everything flowing through the `openai` SDK is captured automatically — messages,
tool calls, token counts, timing, model name.

## Environment variables (fallbacks)

- `LANGPERF_ENDPOINT` — OTLP endpoint base URL (default `http://localhost:4318`)
- `LANGPERF_SERVICE_NAME` — service name shown in the UI
- `LANGPERF_ENVIRONMENT` — maps to OTel `deployment.environment`

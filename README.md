# LangPerf

The agent improvement loop — local OSS self-hosted v1.

## Quick start

```bash
docker compose up -d
pip install -e ./sdk
python scripts/smoke.py   # requires LM Studio (or any OpenAI-compatible endpoint) running
```

Open [http://localhost:3030](http://localhost:3030) to browse trajectories.

## Instrumenting your agent

```python
import langperf, openai

langperf.init(endpoint="http://localhost:4318", service_name="my-agent")

client = openai.OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")
resp = client.chat.completions.create(
    model="gpt-oss-20b",
    messages=[{"role": "user", "content": "hello"}],
)
```

Everything is captured automatically — tokens, timing, messages, tool calls.

## Status

v1 in active development. See [docs/ROADMAP.md](docs/ROADMAP.md) for what's explicitly out of scope for v1.

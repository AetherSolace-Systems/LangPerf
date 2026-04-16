"""M1 smoke test.

Fires a single OpenAI-compatible chat completion against a local endpoint
(LM Studio by default) to verify that spans flow from the `langperf` SDK
through the OTLP exporter and into the langperf-api container's logs.

Usage:

    python scripts/smoke.py

Assumes:
  - `docker compose up -d` is running (langperf-api on :4318)
  - LM Studio (or any OpenAI-compatible server) is reachable at
    http://localhost:1234/v1

If you don't have LM Studio running, set OPENAI_BASE_URL to any other
OpenAI-compatible endpoint.
"""

import os
import sys

import langperf
import openai


def main() -> int:
    langperf.init(
        endpoint=os.environ.get("LANGPERF_ENDPOINT", "http://localhost:4318"),
        service_name="langperf-smoke",
        environment="dev",
    )

    base_url = os.environ.get("OPENAI_BASE_URL", "http://localhost:1234/v1")
    api_key = os.environ.get("OPENAI_API_KEY", "lm-studio")
    model = os.environ.get("SMOKE_MODEL", "local-model")

    print(f"[smoke] calling {base_url}  model={model}")
    client = openai.OpenAI(base_url=base_url, api_key=api_key)
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a terse assistant."},
                {"role": "user", "content": "Reply with one word: ok"},
            ],
            max_tokens=5,
        )
    except Exception as exc:
        print(f"[smoke] OpenAI call failed: {exc}")
        print("[smoke] (this is fine for exporter-only validation — spans for the")
        print("[smoke]  failed call should still flush to the langperf-api logs)")
        langperf.flush()
        return 1

    content = resp.choices[0].message.content if resp.choices else "(no content)"
    print(f"[smoke] response: {content!r}")
    print("[smoke] flushing pending spans…")
    langperf.flush()
    print("[smoke] done — check `docker compose logs langperf-api` for span output")
    return 0


if __name__ == "__main__":
    sys.exit(main())

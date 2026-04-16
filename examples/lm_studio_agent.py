"""End-to-end example: a small multi-step agent traced with LangPerf.

Two LLM calls inside one trajectory, with a `@langperf.node`-decorated tool
call in between. Points at LM Studio (OpenAI-compatible endpoint at localhost)
by default; set OPENAI_BASE_URL / OPENAI_API_KEY / SMOKE_MODEL to override.

Run:

    docker compose up -d
    pip install -e ./sdk openai
    python examples/lm_studio_agent.py
"""

import json
import os

import langperf
import openai


@langperf.node(kind="tool_call", name="lookup_weather")
def lookup_weather(city: str) -> dict:
    # Pretend this called an API. Hardcoded result.
    return {"city": city, "temp_c": 18, "condition": "partly cloudy"}


def main() -> int:
    langperf.init(
        endpoint=os.environ.get("LANGPERF_ENDPOINT", "http://localhost:4318"),
        service_name="lm-studio-demo",
        environment="dev",
    )

    base_url = os.environ.get("OPENAI_BASE_URL", "http://localhost:1234/v1")
    api_key = os.environ.get("OPENAI_API_KEY", "lm-studio")
    model = os.environ.get("SMOKE_MODEL", "local-model")
    client = openai.OpenAI(base_url=base_url, api_key=api_key)

    with langperf.trajectory(name="weather in paris"):
        # 1. first LLM call — ask the model what to do
        plan = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a concise assistant.",
                },
                {
                    "role": "user",
                    "content": "What should I check to know the weather in Paris?",
                },
            ],
            max_tokens=60,
        )
        plan_text = plan.choices[0].message.content or "(empty)"

        # 2. tool call (traced as its own node via the decorator)
        result = lookup_weather("Paris")

        # 3. second LLM call — summarize the result
        client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Respond in one short sentence."},
                {"role": "user", "content": f"Weather data: {json.dumps(result)}. Summarize."},
            ],
            max_tokens=30,
        )

        # 4. a plain inline node to demonstrate the context-manager form
        with langperf.node(kind="reasoning", name="final_thoughts") as span:
            span.set_attribute("langperf.note", "this is a manual span")

    langperf.flush()
    print("[demo] done — open http://localhost:3030 to view the trajectory")
    print(f"[demo] first plan: {plan_text!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

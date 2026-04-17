"""Weather-bot agent — varied queries across envs to populate the dashboard.

Separate file from lm_studio_agent.py so LangPerf fingerprints it as a
distinct Agent (signature = mod:<host>:examples.weather_bot).

    .venv/bin/python examples/weather_bot.py [--runs 5] [--env dev]
"""

from __future__ import annotations

import argparse
import json
import os
import random

import langperf
import openai


CITIES = ("Paris", "Tokyo", "Reykjavik", "Cape Town", "Quito", "Oslo", "Mumbai", "Hanoi")


@langperf.node(kind="tool_call", name="lookup_weather")
def lookup_weather(city: str) -> dict:
    return {
        "city": city,
        "temp_c": random.randint(-5, 32),
        "condition": random.choice(["clear", "partly cloudy", "rain", "overcast"]),
        "wind_kmh": random.randint(2, 40),
    }


@langperf.node(kind="tool_call", name="pack_advice")
def pack_advice(temp_c: int, condition: str) -> dict:
    items = []
    if temp_c < 5:
        items += ["heavy coat", "gloves"]
    elif temp_c < 15:
        items += ["jacket"]
    else:
        items += ["light layers"]
    if "rain" in condition:
        items.append("umbrella")
    return {"pack": items}


def one_run(client: openai.OpenAI, model: str, city: str) -> None:
    with langperf.trajectory(name=f"weather in {city.lower()}"):
        client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful travel concierge. Keep replies short."},
                {"role": "user", "content": f"I'm heading to {city} tomorrow. What should I check?"},
            ],
            max_tokens=80,
        )
        w = lookup_weather(city)
        p = pack_advice(w["temp_c"], w["condition"])
        client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Summarize in one sentence."},
                {
                    "role": "user",
                    "content": f"Weather: {json.dumps(w)}. Packing: {json.dumps(p)}. Give a one-line travel tip.",
                },
            ],
            max_tokens=40,
        )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--env", default=os.environ.get("LANGPERF_ENVIRONMENT", "dev"))
    ap.add_argument("--model", default=os.environ.get("SMOKE_MODEL", "qwen2.5-7b-instruct"))
    args = ap.parse_args()

    langperf.init(
        endpoint=os.environ.get("LANGPERF_ENDPOINT", "http://localhost:4318"),
        service_name="weather-bot",
        environment=args.env,
    )

    client = openai.OpenAI(
        base_url=os.environ.get("OPENAI_BASE_URL", "http://localhost:1234/v1"),
        api_key=os.environ.get("OPENAI_API_KEY", "lm-studio"),
    )

    for i in range(args.runs):
        city = random.choice(CITIES)
        print(f"  [{i + 1}/{args.runs}] env={args.env} city={city}")
        one_run(client, args.model, city)

    langperf.flush()
    print(f"done — {args.runs} runs emitted as agent(weather-bot, env={args.env})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

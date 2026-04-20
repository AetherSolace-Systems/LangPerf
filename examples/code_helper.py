"""Code-helper agent — multi-step: classify → lookup → suggest.

Separate file → distinct agent signature → LangPerf creates a new Agent row.

    .venv/bin/python examples/code_helper.py [--runs 5] [--env prod]
"""

from __future__ import annotations

import argparse
import json
import os
import random

import langperf
import openai


SNIPPETS = (
    ("python", "list comprehension vs map"),
    ("python", "asyncio.gather error handling"),
    ("typescript", "React.useCallback dependencies"),
    ("typescript", "zod schema inference"),
    ("go", "context cancellation propagation"),
    ("rust", "tokio::select! branch fairness"),
    ("sql", "postgres gin index on jsonb"),
)


@langperf.node(kind="tool_call", name="classify_topic")
def classify_topic(question: str) -> dict:
    lang = next((l for (l, k) in SNIPPETS if l in question.lower()), "unknown")
    return {"language": lang, "complexity": random.choice(["low", "med", "high"])}


@langperf.node(kind="tool_call", name="search_docs")
def search_docs(language: str, topic: str) -> dict:
    return {
        "language": language,
        "topic": topic,
        "hits": random.randint(2, 8),
        "top_url": f"https://docs.example/{language}/{topic.replace(' ', '-')}",
    }


def one_run(client: openai.OpenAI, model: str, language: str, topic: str) -> None:
    with langperf.trajectory(name=f"{language}: {topic}"):
        client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a senior engineer. Be concise."},
                {"role": "user", "content": f"Explain {topic} in {language}."},
            ],
            max_tokens=100,
        )
        meta = classify_topic(f"{language} {topic}")
        docs = search_docs(language, topic)
        client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Give one actionable tip."},
                {"role": "user", "content": f"Context: {json.dumps(meta)}. Docs: {json.dumps(docs)}. Tip?"},
            ],
            max_tokens=60,
        )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--env", default=os.environ.get("LANGPERF_ENVIRONMENT", "dev"))
    ap.add_argument("--model", default=os.environ.get("SMOKE_MODEL", "qwen2.5-7b-instruct"))
    args = ap.parse_args()

    langperf.init(
        endpoint=os.environ.get("LANGPERF_ENDPOINT", "http://localhost:4318"),
        agent_name="code-helper",
        environment=args.env,
    )

    client = openai.OpenAI(
        base_url=os.environ.get("OPENAI_BASE_URL", "http://localhost:1234/v1"),
        api_key=os.environ.get("OPENAI_API_KEY", "lm-studio"),
    )

    for i in range(args.runs):
        lang, topic = random.choice(SNIPPETS)
        print(f"  [{i + 1}/{args.runs}] env={args.env} {lang}: {topic}")
        one_run(client, args.model, lang, topic)

    langperf.flush()
    print(f"done — {args.runs} runs emitted as agent(code-helper, env={args.env})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

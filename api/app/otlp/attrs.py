"""Helpers to extract well-known fields from the heterogeneous attribute bag.

Agent trace spans in the wild come from three overlapping semantic conventions:

  1. OTel GenAI semconv   — `gen_ai.*`             (stable, OTel spec)
  2. OpenInference         — `llm.*`, `input.*`,   (Arize convention)
                             `output.*`, `openinference.*`
  3. LangPerf SDK          — `langperf.*`           (our own layer)

These helpers read from all three so the backend doesn't care which instrumentation
produced the span.
"""

from __future__ import annotations

from typing import Any, Optional


def _as_int(v: Any) -> Optional[int]:
    try:
        if v is None:
            return None
        return int(v)
    except (TypeError, ValueError):
        return None


def extract_input_tokens(attrs: dict[str, Any]) -> int:
    """Input (prompt) tokens for a span, or 0 when the attribute is missing."""
    return next(
        (
            n
            for key in ("llm.token_count.prompt", "gen_ai.usage.input_tokens")
            if (n := _as_int(attrs.get(key))) is not None
        ),
        0,
    )


def extract_output_tokens(attrs: dict[str, Any]) -> int:
    """Output (completion) tokens for a span, or 0 when missing."""
    return next(
        (
            n
            for key in ("llm.token_count.completion", "gen_ai.usage.output_tokens")
            if (n := _as_int(attrs.get(key))) is not None
        ),
        0,
    )


def extract_token_count(attrs: dict[str, Any]) -> int:
    """Total tokens for a span, summing input + output if no total is provided."""
    for key in ("llm.token_count.total", "gen_ai.usage.total_tokens"):
        if (n := _as_int(attrs.get(key))) is not None:
            return n
    return extract_input_tokens(attrs) + extract_output_tokens(attrs)


def derive_kind(attrs: dict[str, Any], span_name: str) -> Optional[str]:
    """Normalize the node/span kind across instrumentation conventions.

    Priority: langperf.node.kind > openinference.span.kind > inferred from
    gen_ai/llm attributes.
    """
    if v := attrs.get("langperf.node.kind"):
        return str(v)
    if v := attrs.get("openinference.span.kind"):
        return str(v).lower()
    if "gen_ai.operation.name" in attrs or "llm.system" in attrs:
        return "llm"
    if "tool.name" in attrs:
        return "tool"
    return None

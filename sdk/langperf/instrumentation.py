"""Wire up OpenInference instrumentations.

Currently installs only the OpenAI Python SDK instrumentation. Adding LangChain /
LlamaIndex / etc. is a matter of importing their respective instrumentors here —
all follow the same `.instrument(tracer_provider=...)` pattern.
"""

from __future__ import annotations

import logging

from opentelemetry.sdk.trace import TracerProvider

logger = logging.getLogger("langperf.instrumentation")


def install_instrumentations(tracer_provider: TracerProvider) -> None:
    _install_openai(tracer_provider)


def _install_openai(tracer_provider: TracerProvider) -> None:
    try:
        from openinference.instrumentation.openai import OpenAIInstrumentor
    except ImportError:  # pragma: no cover
        logger.warning(
            "openinference-instrumentation-openai not importable; "
            "openai calls will not be traced"
        )
        return

    # Default config = no `hide_*` flags set = verbose capture of messages, tool
    # args, responses, and all gen_ai.* attributes. Users can opt into redaction
    # via OPENINFERENCE_HIDE_* env vars per the openinference spec.
    OpenAIInstrumentor().instrument(tracer_provider=tracer_provider)
    logger.debug("installed OpenAI instrumentation")

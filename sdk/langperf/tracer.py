"""OTel tracer setup and global state for LangPerf."""

from __future__ import annotations

import logging
import os
from typing import Optional

from opentelemetry import trace as trace_api
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from langperf.instrumentation import install_instrumentations

logger = logging.getLogger("langperf")

_state: dict = {"initialized": False, "provider": None}


def init(
    *,
    endpoint: Optional[str] = None,
    service_name: Optional[str] = None,
    environment: Optional[str] = None,
) -> TracerProvider:
    """Configure LangPerf.

    Sets up an OTel TracerProvider with an OTLP/HTTP exporter and auto-installs
    OpenInference's `openai` instrumentation. Safe to call multiple times; only
    the first call wires up the global provider and instrumentations.

    Resolution order for each argument: explicit kwarg > env var > default.

    Env vars:
        LANGPERF_ENDPOINT       default: http://localhost:4318
        LANGPERF_SERVICE_NAME   default: "langperf-agent"
        LANGPERF_ENVIRONMENT    default: (unset)
    """
    if _state["initialized"]:
        logger.debug("langperf.init() called more than once; ignoring subsequent call")
        return _state["provider"]

    endpoint = endpoint or os.environ.get("LANGPERF_ENDPOINT", "http://localhost:4318")
    service_name = service_name or os.environ.get("LANGPERF_SERVICE_NAME", "langperf-agent")
    environment = environment or os.environ.get("LANGPERF_ENVIRONMENT")

    resource_attrs = {"service.name": service_name}
    if environment:
        resource_attrs["deployment.environment"] = environment
    resource = Resource.create(resource_attrs)

    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=endpoint.rstrip("/") + "/v1/traces")
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace_api.set_tracer_provider(provider)

    install_instrumentations(provider)

    _state["initialized"] = True
    _state["provider"] = provider
    logger.info(
        "langperf initialized: service=%s endpoint=%s env=%s",
        service_name,
        endpoint,
        environment or "-",
    )
    return provider


def flush(timeout_millis: int = 5000) -> bool:
    """Force-flush pending spans through the batch processor.

    Useful for short-lived scripts where the process exits before the batch
    processor's background thread has a chance to ship the final batch.
    """
    provider = _state.get("provider")
    if provider is None:
        return False
    return provider.force_flush(timeout_millis=timeout_millis)

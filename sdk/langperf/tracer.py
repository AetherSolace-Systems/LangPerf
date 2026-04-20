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

from langperf._baggage import LangPerfBaggageSpanProcessor
from langperf.instrumentation import install_instrumentations
from langperf.signature import detect as detect_identity

logger = logging.getLogger("langperf")

_state: dict = {"initialized": False, "provider": None, "identity": None}


def init(
    *,
    endpoint: Optional[str] = None,
    service_name: Optional[str] = None,
    agent_name: Optional[str] = None,
    environment: Optional[str] = None,
    version: Optional[str] = None,
    api_token: Optional[str] = None,
) -> TracerProvider:
    """Configure LangPerf.

    Sets up an OTel TracerProvider with an OTLP/HTTP exporter, registers the
    LangPerf baggage-propagation span processor, and auto-installs
    OpenInference's `openai` instrumentation. Safe to call multiple times;
    only the first call wires up the global provider and instrumentations.

    Also auto-detects this agent's identity (signature + git SHA + package
    version) and attaches it as OTel resource attributes so the LangPerf
    backend can attribute every run to a first-class Agent entity without
    any user registration.

    Identity: the **bearer token** is the source of truth for which
    Agent these traces belong to. ``agent_name=`` is optional and
    advisory — the backend uses the Agent's registered name for display
    regardless of what you pass here. The kwarg is still honored as an
    OTel ``service.name`` resource attribute for interop with other OTel
    tooling, but you no longer need to keep it in sync with the UI.

    Resolution order for each kwarg: explicit kwarg > env var > default.

    Env vars:
        LANGPERF_ENDPOINT       default: http://localhost:4318
        LANGPERF_AGENT_NAME     optional; advisory only. default: "langperf-agent"
        LANGPERF_SERVICE_NAME   deprecated alias for LANGPERF_AGENT_NAME
        LANGPERF_ENVIRONMENT    default: (unset)
        LANGPERF_VERSION        default: (unset)
        LANGPERF_API_TOKEN      required — per-agent bearer token minted in
                                the UI when you register the agent. Identifies
                                the Agent on its own; no other args needed.
    """
    if _state["initialized"]:
        logger.debug("langperf.init() called more than once; ignoring subsequent call")
        return _state["provider"]

    # Deprecation shim for service_name -> agent_name
    if service_name is not None and agent_name is None:
        logger.warning(
            "langperf.init(service_name=...) is deprecated; pass agent_name= instead"
        )
        agent_name = service_name
    elif service_name is not None and agent_name is not None:
        logger.warning(
            "langperf.init got both service_name and agent_name; agent_name wins"
        )

    endpoint = endpoint or os.environ.get("LANGPERF_ENDPOINT", "http://localhost:4318")
    # Prefer LANGPERF_AGENT_NAME; fall back to the deprecated LANGPERF_SERVICE_NAME.
    agent_name = (
        agent_name
        or os.environ.get("LANGPERF_AGENT_NAME")
        or os.environ.get("LANGPERF_SERVICE_NAME")
        or "langperf-agent"
    )
    environment = environment or os.environ.get("LANGPERF_ENVIRONMENT")
    version = version or os.environ.get("LANGPERF_VERSION")
    token = api_token or os.environ.get("LANGPERF_API_TOKEN")
    if not token:
        raise RuntimeError(
            "LANGPERF_API_TOKEN is required. Register an agent in the UI and "
            "set the token via LANGPERF_API_TOKEN or the api_token kwarg."
        )

    # detect() reads the call stack. `_caller_info()` indexes inspect.stack()
    # whose [0] frame is _caller_info itself, [1] is detect, [2] is init (here),
    # [3] is the user script that called init. Use 3 so we fingerprint the user's
    # caller, not our own init() frame.
    identity = detect_identity(caller_stack_offset=3)

    resource_attrs: dict[str, object] = {
        "service.name": agent_name,
        "langperf.agent.signature": identity.signature,
        "langperf.agent.language": identity.language,
    }
    if environment:
        resource_attrs["deployment.environment"] = environment
    if version:
        resource_attrs["service.version"] = version
    if identity.git_origin:
        resource_attrs["langperf.agent.git_origin"] = identity.git_origin
    if identity.git_sha:
        resource_attrs["langperf.agent.version.sha"] = identity.git_sha
    if identity.short_sha:
        resource_attrs["langperf.agent.version.short_sha"] = identity.short_sha
    if identity.package_version:
        resource_attrs["langperf.agent.version.package"] = identity.package_version

    resource = Resource.create(resource_attrs)

    provider = TracerProvider(resource=resource)
    provider.add_span_processor(LangPerfBaggageSpanProcessor())
    exporter = OTLPSpanExporter(
        endpoint=endpoint.rstrip("/") + "/v1/traces",
        headers={"Authorization": f"Bearer {token}"},
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace_api.set_tracer_provider(provider)

    install_instrumentations(provider)

    _state["initialized"] = True
    _state["provider"] = provider
    _state["identity"] = identity
    logger.info(
        "langperf initialized: service=%s endpoint=%s env=%s signature=%s version=%s",
        agent_name,
        endpoint,
        environment or "-",
        identity.signature,
        identity.package_version or identity.short_sha or "-",
    )
    return provider


def flush(timeout_millis: int = 5000) -> bool:
    """Force-flush pending spans through the batch processor."""
    provider = _state.get("provider")
    if provider is None:
        return False
    return provider.force_flush(timeout_millis=timeout_millis)

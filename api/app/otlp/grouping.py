"""Trajectory grouping logic.

A trajectory is a set of spans that share a "trajectory id". The SDK stamps
`langperf.trajectory.id` onto every span in a `with langperf.trajectory(...)`
block (M4+). When that attribute is absent — e.g. raw OpenInference without our
SDK, or ingestion from a third-party OTel source — we fall back to the OTel
`trace_id`, so trajectories still group usefully.

Both values resolve to a UUID string for the `trajectories.id` primary key.
"""

from __future__ import annotations

import uuid
from typing import Any, Optional


def trace_id_to_uuid(trace_id: str) -> str:
    """Convert a 32-hex-char OTel trace_id to canonical UUID form (with dashes)."""
    hex_clean = trace_id.replace("-", "").lower()
    # OTel trace_id is 128 bits = 32 hex chars. If shorter (edge case), left-pad.
    hex_clean = hex_clean.rjust(32, "0")[:32]
    return str(uuid.UUID(hex=hex_clean))


def resolve_trajectory_id(span: dict[str, Any]) -> str:
    """Return the UUID of the trajectory this span belongs to."""
    explicit = span.get("attributes", {}).get("langperf.trajectory.id")
    if explicit:
        # SDK-generated UUID. Accept both canonical and hex forms.
        return str(uuid.UUID(str(explicit)))
    return trace_id_to_uuid(span["trace_id"])


def resolve_trajectory_name(
    span: dict[str, Any], resource_attrs: dict[str, Any]
) -> Optional[str]:
    """Return the trajectory name if available."""
    return span.get("attributes", {}).get("langperf.trajectory.name") or None


def resolve_service_name(resource_attrs: dict[str, Any]) -> str:
    return resource_attrs.get("service.name", "unknown")


def resolve_environment(resource_attrs: dict[str, Any]) -> Optional[str]:
    return resource_attrs.get("deployment.environment")

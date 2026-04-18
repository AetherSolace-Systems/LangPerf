from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class HeuristicHit:
    heuristic: str
    severity: float
    signature: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class HeuristicContext:
    trajectory_id: str
    org_id: str
    spans: list[dict[str, Any]]
    baselines: dict[str, Any]


class Heuristic(Protocol):
    slug: str

    def evaluate(self, ctx: HeuristicContext) -> list[HeuristicHit]: ...

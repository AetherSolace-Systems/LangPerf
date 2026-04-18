import hashlib
from collections import defaultdict
from collections.abc import Iterable
from typing import TypedDict


class HitLike(TypedDict, total=False):
    heuristic: str
    signature: str


def trajectory_signature(hits: Iterable[HitLike]) -> str:
    sigs = sorted({h["signature"] for h in hits if h.get("signature")})
    return "|".join(sigs)


def signature_hash(signature: str) -> str:
    return hashlib.sha1(signature.encode("utf-8")).hexdigest()[:12]


def group_trajectories_by_signature(rows: Iterable[tuple[str, str]]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = defaultdict(list)
    for tid, sig in rows:
        out[sig].append(tid)
    return dict(out)

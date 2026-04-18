"""Auto-generate adjective-noun agent names (docker-style).

Called at first-sight of an unknown agent signature. The generator picks a
random adjective/noun pair and asks the caller to confirm it's unique in the
`agents.name` column. On collision, try again (capped at 50 attempts — if
that fails the word lists are too small).
"""

from __future__ import annotations

import random
from typing import Callable

ADJECTIVES: tuple[str, ...] = (
    "amber", "arctic", "azure", "bold", "brisk", "brave", "bronze",
    "calm", "clever", "cobalt", "copper", "coral", "crimson", "cyan",
    "daring", "deep", "dusty", "eager", "ember", "fabled", "fallow",
    "frosted", "gentle", "gilded", "glacial", "golden", "graceful",
    "hazel", "humble", "icy", "indigo", "iron", "jade", "jovial",
    "lucent", "lunar", "muted", "mystic", "noble", "opal", "pensive",
    "placid", "quiet", "quick", "ruby", "russet", "sable", "savvy",
    "sienna", "silent", "silver", "slate", "solar", "stoic", "storm",
    "swift", "tawny", "thorn", "tidal", "umber", "velvet", "verdant",
    "vermilion", "warm", "whispering", "wild", "windy", "woven",
)

NOUNS: tuple[str, ...] = (
    "anvil", "arrow", "atlas", "beacon", "bison", "blade", "bloom",
    "bolt", "cairn", "cedar", "cipher", "cobra", "comet", "copper",
    "crest", "dagger", "dune", "ember", "falcon", "fern", "flint",
    "forge", "fountain", "garland", "gear", "glyph", "grove", "harbor",
    "hawk", "heron", "ingot", "jaguar", "kettle", "lantern", "lichen",
    "loom", "meadow", "meridian", "mesa", "miner", "moth", "nimbus",
    "oak", "obelisk", "orchard", "otter", "palette", "peregrine",
    "pillar", "pine", "quarry", "quartz", "ranger", "raven", "reef",
    "runner", "sable", "sage", "scribe", "shoal", "shore", "signal",
    "skein", "spring", "summit", "talon", "tinder", "torch", "tundra",
    "valley", "vane", "vintage", "warren", "weaver", "willow", "wren",
    "zenith",
)


def _candidate(rng: random.Random) -> str:
    return f"{rng.choice(ADJECTIVES)}-{rng.choice(NOUNS)}"


def generate_name(
    name_exists: Callable[[str], bool],
    *,
    seed: int | None = None,
    max_attempts: int = 50,
) -> str:
    """Return a fresh "adjective-noun" that passes name_exists() -> False.

    Raises RuntimeError if it can't find a free slot in max_attempts tries.
    """
    rng = random.Random(seed)
    for _ in range(max_attempts):
        candidate = _candidate(rng)
        if not name_exists(candidate):
            return candidate
    raise RuntimeError(
        f"Could not find unused agent name after {max_attempts} attempts — "
        "word lists may be too small"
    )

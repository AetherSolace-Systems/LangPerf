"""backfill — one synthetic Agent per distinct service_name

Any trajectories with agent_id IS NULL get attributed to a synthetic Agent
with signature "legacy:<service_name>" and a docker-style name. Synthetic
Agents get a generic "unknown" version so the FK on trajectories is
populated end-to-end. Idempotent — running twice is a no-op.

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-17 00:02:00
"""

from __future__ import annotations

import random
import uuid

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

ADJECTIVES = (
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
NOUNS = (
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


def _pick_name(taken: set[str], rng: random.Random) -> str:
    for _ in range(200):
        candidate = f"{rng.choice(ADJECTIVES)}-{rng.choice(NOUNS)}"
        if candidate not in taken:
            taken.add(candidate)
            return candidate
    raise RuntimeError("could not find unused agent name during backfill")


def upgrade() -> None:
    conn = op.get_bind()
    rng = random.Random(42)

    taken = {
        row[0]
        for row in conn.execute(sa.text("SELECT name FROM agents")).fetchall()
    }

    rows = conn.execute(
        sa.text(
            """
            SELECT DISTINCT service_name
            FROM trajectories
            WHERE agent_id IS NULL
              AND service_name IS NOT NULL
            """
        )
    ).fetchall()

    for (service_name,) in rows:
        signature = f"legacy:{service_name}"
        existing = conn.execute(
            sa.text("SELECT id, name FROM agents WHERE signature = :sig"),
            {"sig": signature},
        ).fetchone()
        if existing:
            agent_id, name = existing
        else:
            name = _pick_name(taken, rng)
            agent_id = str(uuid.uuid4())
            conn.execute(
                sa.text(
                    """
                    INSERT INTO agents (id, signature, name, description)
                    VALUES (:id, :sig, :name, :desc)
                    """
                ),
                {
                    "id": agent_id,
                    "sig": signature,
                    "name": name,
                    "desc": f"Backfilled from service_name={service_name}",
                },
            )

        version_row = conn.execute(
            sa.text(
                """
                SELECT id FROM agent_versions
                WHERE agent_id = :aid
                  AND git_sha IS NULL
                  AND package_version IS NULL
                """
            ),
            {"aid": agent_id},
        ).fetchone()
        if version_row:
            version_id = version_row[0]
        else:
            version_id = str(uuid.uuid4())
            conn.execute(
                sa.text(
                    """
                    INSERT INTO agent_versions (id, agent_id, label)
                    VALUES (:id, :aid, 'unknown')
                    """
                ),
                {"id": version_id, "aid": agent_id},
            )

        conn.execute(
            sa.text(
                """
                UPDATE trajectories
                   SET agent_id = :aid,
                       agent_version_id = :vid
                 WHERE agent_id IS NULL
                   AND service_name = :svc
                """
            ),
            {"aid": agent_id, "vid": version_id, "svc": service_name},
        )


def downgrade() -> None:
    pass

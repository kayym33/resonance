"""How often and how recently each launcher command was run.

Stays on this device: commands are per platform, habits differ between
computers, and syncing would upload a record on every launch.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone

from .paths import DATA_DIR
from .store import Collection, now_iso, parse_iso

# A use counts for half as much after this many days.
HALF_LIFE_DAYS = 14

# Not in sync.SYNCED, so its records are never uploaded.
USAGE = Collection("usage", DATA_DIR / "usage.json")


@dataclass(frozen=True)
class Usage:
    count: int
    last_used: datetime


def record_use(name: str, collection: Collection = USAGE) -> None:
    """Count one launch of the command called ``name``."""
    previous = collection.get(name) or {}
    try:
        count = int(previous.get("count", 0))
    except (TypeError, ValueError):
        count = 0
    collection.put(name, {"count": count + 1, "last_used": now_iso()})


def load_usage(collection: Collection = USAGE) -> dict[str, Usage]:
    usage: dict[str, Usage] = {}
    for name, data in collection.items():
        try:
            last_used = parse_iso(str(data["last_used"]))
            if last_used.tzinfo is None:
                last_used = last_used.replace(tzinfo=timezone.utc)
            usage[name] = Usage(int(data["count"]), last_used)
        except (KeyError, TypeError, ValueError):
            continue  # A hand-edited or damaged record; ignore it.
    return usage


def frecency(usage: Usage | None, now: datetime) -> float:
    """Higher for commands run more often and more recently.

    Grows with the logarithm of the count, so a long history can't bury a
    new habit, and halves for every HALF_LIFE_DAYS since the last use.
    """
    if usage is None or usage.count <= 0:
        return 0.0
    age_days = max((now - usage.last_used).total_seconds(), 0.0) / 86_400
    return math.log2(1 + usage.count) * 0.5 ** (age_days / HALF_LIFE_DAYS)

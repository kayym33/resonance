from __future__ import annotations

from .paths import DATA_DIR
from .store import Collection

PROFILE = Collection("profile", DATA_DIR / "profile.json")
PROFILE_ID = "me"


def display_name() -> str:
    data = PROFILE.get(PROFILE_ID) or {}
    return str(data.get("display_name", "")).strip()


def set_display_name(name: str) -> None:
    data = dict(PROFILE.get(PROFILE_ID) or {})
    data["display_name"] = name.strip()
    PROFILE.put(PROFILE_ID, data)

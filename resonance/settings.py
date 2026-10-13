from __future__ import annotations

import json
from typing import Any

from .setup import CONFIG_PATH

SETTINGS_PATH = CONFIG_PATH.with_name("settings.json")


def load_settings() -> dict[str, Any]:
    try:
        with SETTINGS_PATH.open(encoding="utf-8") as settings_file:
            settings: object = json.load(settings_file)
    except (OSError, ValueError):
        return {}
    return settings if isinstance(settings, dict) else {}


def save_setting(key: str, value: Any) -> None:
    settings = load_settings()
    if value is None:
        settings.pop(key, None)
    else:
        settings[key] = value
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SETTINGS_PATH.open("w", encoding="utf-8") as settings_file:
        json.dump(settings, settings_file, indent=2)

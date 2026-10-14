"""Preferences: synced ones follow the account, device ones stay put."""

from __future__ import annotations

import json
from typing import Any

from .paths import DATA_DIR
from .store import Collection

# Not synced: things that only make sense for this computer.
DEVICE_SETTINGS_PATH = DATA_DIR / "device.json"


def legacy_settings(raw: object) -> dict[str, dict[str, Any]]:
    """Convert the pre-sync flat {key: value} file."""
    if not isinstance(raw, dict):
        return {}
    return {key: {"value": value} for key, value in raw.items()}


SETTINGS = Collection("setting", DATA_DIR / "settings.json", legacy_settings)


def load_settings() -> dict[str, Any]:
    return {key: data.get("value") for key, data in SETTINGS.items()}


def save_setting(key: str, value: Any) -> None:
    if value is None:
        SETTINGS.delete(key)
    else:
        SETTINGS.put(key, {"value": value})


def load_device_setting(key: str, default: Any = None) -> Any:
    try:
        with DEVICE_SETTINGS_PATH.open(encoding="utf-8") as settings_file:
            settings: object = json.load(settings_file)
    except (OSError, ValueError):
        return default
    return settings.get(key, default) if isinstance(settings, dict) else default


def save_device_setting(key: str, value: Any) -> None:
    try:
        with DEVICE_SETTINGS_PATH.open(encoding="utf-8") as settings_file:
            settings = json.load(settings_file)
    except (OSError, ValueError):
        settings = {}
    settings[key] = value
    DEVICE_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with DEVICE_SETTINGS_PATH.open("w", encoding="utf-8") as settings_file:
        json.dump(settings, settings_file, indent=2)

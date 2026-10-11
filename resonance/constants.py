from __future__ import annotations

import json
from pathlib import Path
from typing import Any


QUOTES_PATH: Path = Path(__file__).resolve().parents[1] / "assets" / "quotes.json"
APP_VERSION = "0.1.2"
APP_AUTHOR = "kayla"
APP_EMAIL = "kayla.mcdade.2023@uni.strath.ac.uk"
APP_REPOSITORY = "https://github.com/kayym33/resonance"
MIN_LOADING_TIME: float = 1
GITHUB_RELEASES_API = (
    "https://api.github.com/repos/kayym33/resonance/releases/latest"
)
APP_SIZES: dict[str, tuple[str, float]] = {
    "80": ("300x470", 0.9),
    "90": ("320x480", 1.0),
    "100": ("340x500", 1.0),
    "110": ("350x475", 1.1),
    "120": ("375x500", 1.2),
    "130": ("410x550", 1.3),
}


def load_quotes() -> tuple[str, ...]:
    with QUOTES_PATH.open(encoding="utf-8") as quotes_file:
        quotes: Any = json.load(quotes_file)

    if not isinstance(quotes, list) or not all(
        isinstance(quote, str) for quote in quotes
    ):
        raise ValueError("assets/quotes.json must contain a list of strings")

    return tuple(quotes)


QUOTES: tuple[str, ...] = load_quotes()

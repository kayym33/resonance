from __future__ import annotations

import json
from pathlib import Path
from typing import Any


QUOTES_PATH: Path = Path(__file__).resolve().parents[1] / "assets" / "quotes.json"
APP_VERSION = "0.1.4"
APP_AUTHOR = "kayla"
APP_EMAIL = "kayla.mcdade.2023@uni.strath.ac.uk"
APP_REPOSITORY = "https://github.com/kayym33/resonance"
GITHUB_RELEASES_API = (
    "https://api.github.com/repos/kayym33/resonance/releases/latest"
)
APP_SIZES: dict[str, tuple[str, float]] = {
    "Small": ("260x350", 1.0),
    "Medium": ("320x450", 1.0),
    "Large": ("375x500", 1.25),
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



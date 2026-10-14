from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


QUOTES_PATH: Path = Path(__file__).resolve().parents[1] / "assets" / "quotes.json"
APP_NAME = "t1ld3"
APP_VERSION = "0.1.6"
APP_AUTHOR = "kayla"
APP_EMAIL = "kayla.mcdade.2023@uni.strath.ac.uk"
APP_REPOSITORY = "https://github.com/kayym33/resonance"
MIN_LOADING_TIME: float = 1
# Public by design: Spotify's PKCE login needs no client secret. People
# must still be added under User Management in the Spotify dashboard.
SPOTIFY_CLIENT_ID = "27ad76d41d944e17b2a571fd559f0e32"
SPOTIFY_REDIRECT_URI = "http://127.0.0.1:8888/callback"
# Public by design: the publishable key only reaches what the database's
# row-level security allows (each user's own rows). Never put the
# service_role key in the app.
SUPABASE_URL = "https://zuzpyrwoovdavbuqrqpx.supabase.co"
SUPABASE_KEY = "sb_publishable_OXVfSivrBGVRZL1wr4J9Fw_xUql8kyQ"
GITHUB_RELEASES_API = (
    "https://api.github.com/repos/kayym33/resonance/releases/latest"
)
# Palette colours are (day, night) pairs. CTk widgets switch between
# them by themselves; anything else (canvases, Pillow images, plain Tk
# widgets) resolves them with theme.color() and redraws on a switch.
BACKGROUND = ("#E7E7DD", "#121311")
INK = ("#111210", "#E7E7DD")
INK_SOFT = ("#3B3C37", "#C6C6BA")
MUTED = ("#6B6C63", "#8F9086")
FAINT = ("#A6A79B", "#4D4E47")
RULE = ("#CBCBBF", "#33342F")
HOVER = ("#D8D8CD", "#262722")
ACCENT = ("#E8642C", "#E8642C")
# Orange text and outlines; lighter at night so it stays readable.
ACCENT_DARK = ("#B44718", "#F08A5D")
FIELD = ("#F0F0E8", "#1B1C19")
# The pixel figure in the album art keeps its colours in both themes.
FIGURE_COLOR = "#E8642C"
FIGURE_SHADE = "#B44718"
ALBUM_ART_SIZE = 168
MONO_FONT = "Consolas" if os.name == "nt" else "DejaVu Sans Mono"
# Extra zoom on top of every size preset. Tk on Linux doesn't follow the
# desktop's display scaling, so high-DPI screens need it; on Windows,
# customtkinter already scales by the Windows display setting.
UI_SCALE: float = 1.0 if os.name == "nt" else 4 / 3
DEFAULT_SIZE = "100"
APP_SIZES: dict[str, tuple[str, float]] = {
    name: (geometry, round(scaling * UI_SCALE, 3))
    for name, (geometry, scaling) in {
        "80": ("300x562", 0.9),
        "90": ("320x540", 1.0),
        "100": ("340x560", 1.0),
        "110": ("350x535", 1.1),
        "120": ("375x560", 1.2),
        "130": ("410x610", 1.3),
    }.items()
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





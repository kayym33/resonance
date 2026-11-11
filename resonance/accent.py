"""The accent colour, chosen from a few presets and synced like the theme.

The app stays bone and ink; the accent colours the decorative parts (the
player's sliders, the calendar's "now" line, favourite stars, the pixel
figure) and a share of the ASCII noise ("specks"). Error and warning text
keeps WARNING whatever the accent is, so a problem still looks like one.

A flag preset gives its stripes to the figure and the specks, and one of
its colours to everything else. phone/js/accent.js holds the same presets;
tests/test_logic.py checks they agree.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable

from .theme import Color, pick

# Shares of glyphs coloured: the noise band and stars, and the album art.
SPECK_SHARE = 0.25
ART_SPECK_SHARE = 0.18
# White flag stripes vanish on bone, so the day theme uses this grey.
DAY_WHITE = "#9A9B90"
WHITES = {"#FFFFFF", "#F2EFE8"}


@dataclass(frozen=True)
class Accent:
    label: str
    # Shapes and specks, then text (darker by day, lighter at night).
    mark: tuple[str, str]
    text: tuple[str, str]
    # A flag's colours, top to bottom; empty for a plain colour.
    stripes: tuple[str, ...] = ()


PRESETS: dict[str, Accent] = {
    "orange": Accent("orange", ("#E8642C", "#E8642C"), ("#B44718", "#F08A5D")),
    "ochre": Accent("ochre", ("#C08A1E", "#D6A23A"), ("#7C5806", "#DDB04F")),
    "moss": Accent("moss", ("#6B8A3A", "#86A852"), ("#4A6324", "#A3C27A")),
    "slate": Accent("slate", ("#4F6F8F", "#7193B4"), ("#3A5878", "#8FAECB")),
    "plum": Accent("plum", ("#8A4F7D", "#B07AA3"), ("#6E3A63", "#C493B8")),
    "rose": Accent("rose", ("#C7647A", "#D97F92"), ("#9B3E54", "#E596A8")),
    "trans": Accent(
        "trans",
        ("#5A93AF", "#86BCD4"),
        ("#386C86", "#8EC3DA"),
        ("#7FB3CC", "#DDA5B1", "#F2EFE8", "#DDA5B1", "#7FB3CC"),
    ),
    "lesbian": Accent(
        "lesbian",
        ("#C24F8C", "#DC7DB0"),
        ("#9A2F69", "#E59AC2"),
        ("#B4532F", "#CC8150", "#DDA57A", "#F2EFE8", "#D46FA6", "#BA5292", "#962E66"),
    ),
}
DEFAULT = "orange"

_current: str = DEFAULT
_listeners: list[Callable[[], None]] = []


def name() -> str:
    return _current


def current() -> Accent:
    return PRESETS[_current]


def set_accent(choice: object) -> bool:
    """Switch to the preset called ``choice`` (anything unknown means the
    default) and redraw what uses it. True if it changed."""
    global _current
    chosen = choice if isinstance(choice, str) and choice in PRESETS else DEFAULT
    if chosen == _current:
        return False
    _current = chosen
    for callback in list(_listeners):
        callback()
    return True


def watch(callback: Callable[[], None]) -> None:
    """Call ``callback`` after every accent change. Pair with unwatch()."""
    _listeners.append(callback)


def unwatch(callback: Callable[[], None]) -> None:
    if callback in _listeners:
        _listeners.remove(callback)


def mark() -> Color:
    return current().mark


def text() -> Color:
    return current().text


def visible(colour: str, night: bool) -> str:
    return DAY_WHITE if colour in WHITES and not night else colour


def speck_colors(night: bool) -> tuple[str, ...]:
    """The colours specks are drawn from: a flag's stripes, or the mark."""
    accent = current()
    if accent.stripes:
        return tuple(visible(stripe, night) for stripe in accent.stripes)
    return (pick(accent.mark, night),)


def speck(rng: random.Random, night: bool, share: float = SPECK_SHARE) -> str | None:
    """A speck colour for one glyph, or None to leave it grey."""
    if rng.random() >= share:
        return None
    return rng.choice(speck_colors(night))


def figure_rows(rows: int, night: bool) -> list[str]:
    """The pixel figure's colour for each of its ``rows``: a flag spread
    over the rows, one stripe per band, or the mark on every row."""
    accent = current()
    if not accent.stripes:
        return [pick(accent.mark, night)] * rows
    stripes = accent.stripes
    return [
        stripes[min(len(stripes) - 1, row * len(stripes) // rows)] for row in range(rows)
    ]

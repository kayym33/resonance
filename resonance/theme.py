"""Day and night themes.

Palette constants are (day, night) pairs. customtkinter widgets repaint
themselves when the appearance mode changes; everything else resolves
colours with color() when drawing and registers a redraw with watch().
"""

from __future__ import annotations

from typing import Callable

import customtkinter

Color = str | tuple[str, str]

_listeners: list[Callable[[], None]] = []


def is_night() -> bool:
    return customtkinter.get_appearance_mode() == "Dark"


def pick(value: Color, night: bool) -> str:
    if isinstance(value, str):
        return value
    return value[1] if night else value[0]


def color(value: Color) -> str:
    """The colour to use right now."""
    return pick(value, is_night())


def watch(callback: Callable[[], None]) -> None:
    """Call ``callback`` after every theme switch. Pair with unwatch()."""
    _listeners.append(callback)


def unwatch(callback: Callable[[], None]) -> None:
    if callback in _listeners:
        _listeners.remove(callback)


def set_night(night: bool) -> None:
    if night == is_night():
        return
    customtkinter.set_appearance_mode("dark" if night else "light")
    for callback in list(_listeners):
        callback()

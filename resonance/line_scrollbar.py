"""A thin scrollbar in the app's line style: a 1px rule with an ink thumb.

CTkScrollbar draws a filled slab and runs ``update_idletasks`` on every
draw, which lays out the whole window again. This one is a plain canvas,
so it resolves colours with ``theme.color()`` and scales by hand.
"""
from __future__ import annotations

import tkinter as tk
from typing import Callable

import customtkinter

from .constants import BACKGROUND, INK, INK_SOFT, RULE
from .theme import color, unwatch, watch

WIDTH = 12
THUMB_WIDTH = 3
MIN_THUMB = 24


class LineScrollbar(tk.Canvas):
    """Vertical. Use like a Tk scrollbar: ``command`` is the scrolled
    widget's ``yview``, and its ``yscrollcommand`` is ``set``."""

    def __init__(self, parent: tk.Misc, command: Callable[..., object]) -> None:
        self.scaling = customtkinter.ScalingTracker.get_widget_scaling(parent)
        super().__init__(
            parent,
            width=round(WIDTH * self.scaling),
            bd=0,
            highlightthickness=0,
        )
        self.command = command
        self.first: float = 0.0
        self.last: float = 1.0
        self.hovered: bool = False
        # Where in the thumb the drag started, as a fraction of the bar.
        self.drag_offset: float | None = None
        self.bind("<Configure>", lambda _event: self.redraw())
        self.bind("<Enter>", lambda _event: self.set_hover(True))
        self.bind("<Leave>", lambda _event: self.set_hover(False))
        self.bind("<ButtonPress-1>", self.on_press)
        self.bind("<B1-Motion>", self.on_drag)
        self.bind("<ButtonRelease-1>", self.on_release)
        watch(self.redraw)

    def set(self, first: str | float, last: str | float) -> None:
        self.first, self.last = float(first), float(last)
        self.redraw()

    def rescale(self) -> None:
        self.scaling = customtkinter.ScalingTracker.get_widget_scaling(self)
        self.configure(width=round(WIDTH * self.scaling))
        self.redraw()

    def thumb_span(self) -> tuple[float, float]:
        height = max(1, self.winfo_height())
        top = self.first * height
        bottom = max(self.last * height, top + MIN_THUMB * self.scaling)
        return top, min(bottom, height)

    def redraw(self) -> None:
        self.delete("all")
        self.configure(bg=color(BACKGROUND))
        if self.first <= 0 and self.last >= 1:
            return  # Everything fits; nothing to scroll.
        width = self.winfo_width()
        middle = width // 2
        self.create_line(middle, 0, middle, self.winfo_height(), fill=color(RULE))
        top, bottom = self.thumb_span()
        thumb = round((THUMB_WIDTH + (1 if self.hovered or self.drag_offset is not None else 0)) * self.scaling)
        self.create_rectangle(
            middle - thumb // 2,
            top,
            middle - thumb // 2 + thumb,
            bottom,
            fill=color(INK if self.hovered or self.drag_offset is not None else INK_SOFT),
            width=0,
        )

    def set_hover(self, hovered: bool) -> None:
        self.hovered = hovered
        self.redraw()

    def fraction(self, y: int) -> float:
        return y / max(1, self.winfo_height())

    def on_press(self, event: tk.Event[tk.Misc]) -> None:
        top, bottom = self.thumb_span()
        if top <= event.y <= bottom:
            self.drag_offset = self.fraction(event.y) - self.first
            self.redraw()
        else:
            # A click on the track pages towards it.
            self.command("scroll", -1 if event.y < top else 1, "pages")

    def on_drag(self, event: tk.Event[tk.Misc]) -> None:
        if self.drag_offset is not None:
            self.command("moveto", self.fraction(event.y) - self.drag_offset)

    def on_release(self, _event: tk.Event[tk.Misc]) -> None:
        self.drag_offset = None
        self.redraw()

    def destroy(self) -> None:
        unwatch(self.redraw)
        super().destroy()

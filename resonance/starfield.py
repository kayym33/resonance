from __future__ import annotations

import random
import tkinter as tk
import tkinter.font as tkfont

import customtkinter

from .ascii_art import NOISE_MARKS, blend_rgb, hex_to_rgb
from .constants import BACKGROUND, FAINT, MONO_FONT
from .theme import color, unwatch, watch
from .windows import cancel_pending_after

TWINKLE_MS = 200
# Share of cells re-rolled on each twinkle.
TWINKLE_AMOUNT = 0.02
# Unscaled size of one character cell.
CELL_WIDTH, CELL_HEIGHT = 8, 13


def faded(start: str, end: str, amount: float) -> str:
    red, green, blue = blend_rgb(hex_to_rgb(start), hex_to_rgb(end), amount)
    return f"#{red:02x}{green:02x}{blue:02x}"


def star_colors() -> tuple[str, ...]:
    """Two depths of star: the usual faint grey, and one further back."""
    star, paper = color(FAINT), color(BACKGROUND)
    return (star, star, faded(star, paper, 0.45))


class Starfield(tk.Canvas):
    """Scattered, twinkling ASCII stars that fill whatever space they get.

    Density runs from ``density_top`` at the top edge to
    ``density_bottom`` at the bottom, so a field can fade in or out.
    It's a plain canvas, so sizes are scaled by hand like the calendar.
    """

    def __init__(
        self,
        parent: tk.Misc,
        density_top: float,
        density_bottom: float,
        height: int = 0,
    ) -> None:
        scaling = customtkinter.ScalingTracker.get_widget_scaling(parent)
        super().__init__(
            parent,
            bg=color(BACKGROUND),
            height=round(height * scaling),
            highlightthickness=0,
            bd=0,
        )
        self.density_top = density_top
        self.density_bottom = density_bottom
        self.rng = random.Random()
        self.rows = 0
        self.columns = 0
        self.stars: dict[tuple[int, int], int] = {}
        self.font: tkfont.Font | None = None
        self.colors: tuple[str, ...] = star_colors()
        self.bind("<Configure>", lambda _event: self.fill())
        self.after(TWINKLE_MS, self.twinkle)
        watch(self.retheme)

    def retheme(self) -> None:
        self.configure(bg=color(BACKGROUND))
        self.colors = star_colors()
        self.fill()

    def density(self, row: int) -> float:
        position = row / max(1, self.rows - 1)
        return self.density_top + (self.density_bottom - self.density_top) * position

    def fill(self) -> None:
        scaling = customtkinter.ScalingTracker.get_widget_scaling(self)
        self.font = tkfont.Font(family=MONO_FONT, size=-round(9 * scaling))
        self.delete("all")
        self.stars = {}
        self.columns = int(self.winfo_width() / (CELL_WIDTH * scaling)) + 1
        self.rows = int(self.winfo_height() / (CELL_HEIGHT * scaling)) + 1
        for row in range(self.rows):
            for column in range(self.columns):
                self.reroll(column, row)

    def reroll(self, column: int, row: int) -> None:
        cell = (column, row)
        if cell in self.stars:
            self.delete(self.stars.pop(cell))
        if self.rng.random() >= self.density(row):
            return
        scaling = customtkinter.ScalingTracker.get_widget_scaling(self)
        self.stars[cell] = self.create_text(
            (column + 0.5) * CELL_WIDTH * scaling,
            (row + 0.5) * CELL_HEIGHT * scaling,
            text=self.rng.choice(NOISE_MARKS),
            fill=self.rng.choice(self.colors),
            font=self.font,
        )

    def twinkle(self) -> None:
        cells = self.rows * self.columns
        for _ in range(round(cells * TWINKLE_AMOUNT) if cells else 0):
            self.reroll(
                self.rng.randrange(self.columns),
                self.rng.randrange(self.rows),
            )
        self.after(TWINKLE_MS, self.twinkle)

    def destroy(self) -> None:
        unwatch(self.retheme)
        cancel_pending_after(self)
        super().destroy()

from __future__ import annotations

import random
import tkinter as tk
import tkinter.font as tkfont


from . import accent
from .ascii_art import noise_char
from .constants import BACKGROUND, FAINT, MONO_FONT
from .rich_text import set_font, widget_scaling
from .theme import color, is_night, unwatch, watch
from .windows import cancel_pending_after

FLICKER_MS = 160
FLICKER_AMOUNT = 0.05
# Unscaled font size and line height, as the label this replaced had.
FONT_PX = 10
LINE_PX = 11


class NoiseBand(tk.Text):
    """Rows of faint, flickering ASCII noise, like a starfield, with a
    share of the marks in the accent colour ("specks").

    ``densities`` gives each row's share of marks, top row first, so a
    band can thin out towards the content. One plain Tk text widget, so
    each mark can have its own colour; it follows the theme, the accent
    and the app's scaling by hand.
    """

    def __init__(
        self,
        parent: tk.Misc,
        columns: int,
        densities: tuple[float, ...],
    ) -> None:
        self.rng = random.Random()
        self.densities = densities
        self.font = tkfont.Font(family=MONO_FONT, size=-FONT_PX)
        super().__init__(
            parent,
            width=1,
            height=len(densities),
            bd=0,
            padx=0,
            pady=0,
            wrap="none",
            cursor="arrow",
            takefocus=0,
            highlightthickness=0,
            font=self.font,
            state="disabled",
        )
        # Plain marks, then each speck's colour slot (or -1 for none).
        self.marks: list[list[str]] = [
            [noise_char(self.rng, density) for _ in range(columns)] for density in densities
        ]
        self.specks: list[list[int]] = [[self.new_speck() for _ in range(columns)] for _ in densities]
        # Not a text field: no class bindings, so clicks don't select or
        # take focus, but the window's own bindings still see them.
        self.bindtags((str(self), str(self.winfo_toplevel()), "all"))
        self.retheme()
        watch(self.retheme)
        accent.watch(self.retheme)
        self.bind("<Configure>", lambda _event: self.rescale())
        self.after(FLICKER_MS, self.flicker)

    def new_speck(self) -> int:
        if self.rng.random() >= accent.SPECK_SHARE:
            return -1
        return self.rng.randrange(len(accent.speck_colors(False)))

    def rescale(self) -> None:
        scaling = widget_scaling(self)
        set_font(self.font, size=-round(FONT_PX * scaling))
        line = round(LINE_PX * scaling)
        spacing = max(0, line - self.font.metrics("linespace"))
        self.tag_configure("line", spacing1=spacing // 2, spacing3=spacing - spacing // 2, justify="center")

    def retheme(self) -> None:
        self.configure(bg=color(BACKGROUND), fg=color(FAINT))
        colors = accent.speck_colors(is_night())
        # Slots outlive a change of preset, so wrap them onto the new one.
        self.speck_tags = [f"speck{index}" for index in range(len(colors))]
        for tag, speck_color in zip(self.speck_tags, colors):
            self.tag_configure(tag, foreground=speck_color)
        self.rescale()
        self.draw()

    def draw(self) -> None:
        self.configure(state="normal")
        self.delete("1.0", "end")
        for row_index, (marks, specks) in enumerate(zip(self.marks, self.specks)):
            if row_index:
                self.insert("end", "\n", ("line",))
            # Runs of the same colour, so a row is a handful of inserts.
            run, run_tag = "", None
            for mark, slot in zip(marks, specks):
                tag = self.speck_tags[slot % len(self.speck_tags)] if slot >= 0 and mark != " " else None
                if tag != run_tag and run:
                    self.insert("end", run, ("line", run_tag) if run_tag else ("line",))
                    run = ""
                run_tag = tag
                run += mark
            if run:
                self.insert("end", run, ("line", run_tag) if run_tag else ("line",))
        self.configure(state="disabled")

    def flicker(self) -> None:
        """Re-roll a few marks, like a weak terminal signal."""
        for marks, specks, density in zip(self.marks, self.specks, self.densities):
            for _ in range(max(1, round(len(marks) * FLICKER_AMOUNT))):
                column = self.rng.randrange(len(marks))
                marks[column] = noise_char(self.rng, density)
                specks[column] = self.new_speck()
        self.draw()
        self.after(FLICKER_MS, self.flicker)

    def destroy(self) -> None:
        unwatch(self.retheme)
        accent.unwatch(self.retheme)
        cancel_pending_after(self)
        super().destroy()

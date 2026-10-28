"""Text-heavy views drawn in a single Tk widget each.

Every window Tk maps costs about 15ms on a typical Linux desktop (more
for customtkinter widgets, which are two or three windows each), so a
list built from a label per line takes seconds to appear. ``RichText``
draws formatted, clickable lines in one ``tk.Text``; ``ChipCanvas`` draws
wrapping rows of tag chips on one canvas. Neither is a customtkinter
widget, so both resolve colours with ``theme.color()``, redraw on a
theme switch, and scale their own fonts (call ``rescale`` after a size
change).
"""
from __future__ import annotations

import math
import tkinter as tk
import tkinter.font as tkfont
from typing import Callable

import customtkinter

from .constants import BACKGROUND, HOVER, INK, INK_SOFT, MONO_FONT, MUTED, RULE
from .theme import Color, color, unwatch, watch

# name: (size, weight, colour, slant)
STYLES: dict[str, tuple[int, str, Color, str]] = {
    "heading": (10, "bold", MUTED, "roman"),
    "body": (12, "normal", INK_SOFT, "roman"),
    "strong": (12, "bold", INK, "roman"),
    "number": (12, "bold", MUTED, "roman"),
    "faded": (12, "normal", MUTED, "roman"),
    "muted": (10, "normal", MUTED, "roman"),
    "hint": (10, "normal", MUTED, "italic"),
    "clock": (13, "bold", INK, "roman"),
    "alert": (13, "bold", ("#B44718", "#F08A5D"), "roman"),
}
ROW_PADDING = 4
PARAGRAPH_GAP = 6
HANGING_INDENT = 34


def widget_scaling(widget: tk.Misc) -> float:
    return customtkinter.ScalingTracker.get_widget_scaling(widget)


def set_font(font: tkfont.Font, **options: object) -> None:
    """Configure a font only if something changed. Reconfiguring a Tk
    font, even to the same size, makes Tk re-measure every widget in the
    app, which lays out the whole hub again (about 200ms here)."""
    if any(str(font.cget(key)) != str(value) for key, value in options.items()):
        font.configure(**options)


def scaled_pad(
    widget: tk.Misc,
    pad: int | tuple[int, int],
) -> int | tuple[int, int]:
    """Padding for packing a plain Tk widget. customtkinter scales the
    padding given to its own widgets' pack(), but not to these, so
    without this they sit closer to their neighbours."""
    scaling = widget_scaling(widget)
    if isinstance(pad, tuple):
        return (round(pad[0] * scaling), round(pad[1] * scaling))
    return round(pad * scaling)


class RichText(tk.Text):
    """Read-only formatted text. Lines added with ``row`` and spans added
    with ``link`` are clickable and highlight under the pointer."""

    def __init__(self, parent: tk.Misc, height: int = 1) -> None:
        super().__init__(
            parent,
            height=height,
            width=1,
            bd=0,
            highlightthickness=0,
            padx=0,
            pady=0,
            wrap="word",
            cursor="arrow",
            takefocus=0,
            state="disabled",
            # Read-only, so never show the text cursor.
            insertwidth=0,
            exportselection=False,
        )
        self.fonts: dict[str, tkfont.Font] = {}
        self.commands: dict[str, Callable[[], None]] = {}
        self.hovered: str | None = None
        self.links: int = 0
        self.bind("<Motion>", self.on_motion)
        self.bind("<Leave>", lambda _event: self.set_hover(None))
        # Returning "break" also stops the click selecting text or taking
        # focus from the launcher.
        self.bind("<Button-1>", self.on_click)
        self.bind("<B1-Motion>", lambda _event: "break")
        self.bind("<Double-Button-1>", lambda _event: "break")
        self.bind("<Configure>", lambda _event: self.place_right_tab())
        self.rescale()
        watch(self.retheme)

    def rescale(self) -> None:
        scaling = widget_scaling(self)
        for name, (size, weight, _color, slant) in STYLES.items():
            font = self.fonts.get(name)
            options = {
                "family": MONO_FONT,
                "size": -round(size * scaling),
                "weight": weight,
                "slant": slant,
            }
            if font is None:
                self.fonts[name] = tkfont.Font(**options)
            else:
                set_font(font, **options)
        self.tag_configure("row", spacing1=round(ROW_PADDING * scaling), spacing3=round(ROW_PADDING * scaling))
        self.tag_configure("gap", spacing3=round(PARAGRAPH_GAP * scaling))
        self.tag_configure("space", spacing1=round(14 * scaling))
        self.tag_configure(
            "hang",
            lmargin1=0,
            lmargin2=round(HANGING_INDENT * scaling),
            tabs=(round(HANGING_INDENT * scaling),),
        )
        # Wrapped checklist lines start under the text, after "[ ] ".
        self.tag_configure("checklist", lmargin2=self.fonts["strong"].measure("[ ] "))
        self.tag_configure("struck", overstrike=True)
        self.retheme()
        self.place_right_tab()

    def retheme(self) -> None:
        self.configure(
            bg=color(BACKGROUND),
            fg=color(INK_SOFT),
            selectbackground=color(BACKGROUND),
            inactiveselectbackground=color(BACKGROUND),
            font=self.fonts["body"],
        )
        for name, (_size, _weight, style_color, _slant) in STYLES.items():
            self.tag_configure(name, font=self.fonts[name], foreground=color(style_color))
        self.tag_configure("hover", background=color(HOVER))
        # Styles win over row backgrounds, so hover shows under any text.
        self.tag_lower("hover")

    def place_right_tab(self) -> None:
        """Text after a tab in a row lines up on the right edge."""
        width = max(1, self.winfo_width() - round(8 * widget_scaling(self)))
        self.tag_configure("row", tabs=(width, "right"))

    # Writing

    def clear(self) -> None:
        self.configure(state="normal")
        self.delete("1.0", "end")
        self.configure(state="disabled")
        self.commands = {}
        self.hovered = None
        self.links = 0

    def write(self, text: str, *tags: str) -> None:
        self.configure(state="normal")
        self.insert("end", text, tags)
        self.configure(state="disabled")

    def heading(self, text: str, first: bool = False) -> None:
        if not first:
            self.write("\n", "space")
        self.write(text.upper() + "\n", "heading", "gap")

    def row(
        self,
        row_id: str,
        left: str,
        right: str,
        command: Callable[[], None],
        left_style: str = "strong",
        right_style: str = "muted",
    ) -> None:
        tag = f"row:{row_id}"
        self.commands[tag] = command
        self.write(left, left_style, "row", tag)
        self.write(f"\t{right}\n" if right else "\n", right_style, "row", tag)

    def link(self, text: str, command: Callable[[], None], *tags: str) -> None:
        """A clickable span within a line, such as a checkbox."""
        self.links += 1
        tag = f"link:{self.links}"
        self.commands[tag] = command
        self.write(text, *tags, tag)

    def fit_height(self) -> None:
        """Make the widget exactly as tall as its text, for short blocks
        that shouldn't scroll. Tk counts height in lines of the base font,
        so the padded rows are measured in pixels."""
        self.update_idletasks()
        pixels = self.count("1.0", "end", "update", "ypixels")
        if isinstance(pixels, tuple):
            pixels = pixels[0]
        line = self.fonts["body"].metrics("linespace")
        self.configure(height=max(1, math.ceil((pixels or line) / line)))

    def end_text(self) -> None:
        """Drop the newline after the last line, so no blank line shows."""
        self.configure(state="normal")
        if self.get("end-2c") == "\n":
            self.delete("end-2c")
        self.configure(state="disabled")

    # Pointer

    def row_at(self, event: tk.Event[tk.Misc]) -> str | None:
        index = self.index(f"@{event.x},{event.y}")
        # Below the last line, Tk still reports the last line's index.
        line = self.dlineinfo(index)
        if line is None or event.y > line[1] + line[3]:
            return None
        tags = self.tag_names(index)
        # A link inside a row wins over the row.
        return next((tag for tag in tags if tag.startswith("link:")), None) or next(
            (tag for tag in tags if tag.startswith("row:")), None
        )

    def on_motion(self, event: tk.Event[tk.Misc]) -> None:
        self.set_hover(self.row_at(event))

    def set_hover(self, tag: str | None) -> None:
        if tag == self.hovered:
            return
        self.tag_remove("hover", "1.0", "end")
        self.hovered = tag
        if tag is not None:
            ranges = self.tag_ranges(tag)
            if ranges:
                self.tag_add("hover", ranges[0], ranges[-1])
        self.configure(cursor="hand2" if tag else "arrow")

    def on_click(self, event: tk.Event[tk.Misc]) -> str:
        tag = self.row_at(event)
        if tag is not None and tag in self.commands:
            # After the click finishes, since the command may clear this.
            self.after_idle(self.commands[tag])
        return "break"

    def destroy(self) -> None:
        unwatch(self.retheme)
        super().destroy()


class TextField(tk.Text):
    """A multi-line input with a 1px ink border, for forms. CTkTextbox
    always creates two CTkScrollbars, whose drawing forces a layout pass
    of the whole window (seconds of work per textbox); the mouse wheel
    still scrolls this one."""

    def __init__(self, parent: tk.Misc, height: int) -> None:
        # ``height`` in unscaled pixels, like a CTk widget's.
        self.unscaled_height = height
        self.font = tkfont.Font(family=MONO_FONT, size=-round(12 * widget_scaling(parent)))
        super().__init__(
            parent,
            width=1,
            bd=0,
            wrap="word",
            undo=True,
            font=self.font,
        )
        self.rescale()
        watch(self.retheme)

    def rescale(self) -> None:
        scaling = widget_scaling(self)
        set_font(self.font, size=-round(12 * scaling))
        lines = max(1, round(self.unscaled_height * scaling / self.font.metrics("linespace")))
        self.configure(
            height=lines,
            padx=round(6 * scaling),
            pady=round(4 * scaling),
            highlightthickness=max(1, round(scaling)),
        )
        self.retheme()

    def retheme(self) -> None:
        self.configure(
            bg=color(BACKGROUND),
            fg=color(INK),
            insertbackground=color(INK),
            selectbackground=color(HOVER),
            selectforeground=color(INK),
            highlightbackground=color(INK),
            highlightcolor=color(INK),
        )

    def destroy(self) -> None:
        unwatch(self.retheme)
        super().destroy()


class ChipCanvas(tk.Canvas):
    """Groups of tag chips that wrap to the width given. Chips in
    ``selected`` are drawn filled."""

    CHIP_HEIGHT = 24
    GAP = 6
    PADDING = 11

    def __init__(
        self,
        parent: tk.Misc,
        width: int,
        on_click: Callable[[str], None],
    ) -> None:
        self.unscaled_width = width
        super().__init__(
            parent,
            width=round(width * widget_scaling(parent)),
            height=1,
            bd=0,
            highlightthickness=0,
        )
        self.on_click = on_click
        self.groups: list[tuple[str, list[tuple[str, str]]]] = []
        self.selected: set[str] = set()
        scaling = widget_scaling(parent)
        self.font = tkfont.Font(family=MONO_FONT, size=-round(11 * scaling))
        self.heading_font = tkfont.Font(family=MONO_FONT, size=-round(10 * scaling), weight="bold")
        self.redraw()
        watch(self.redraw)

    def set_groups(
        self,
        groups: list[tuple[str, list[tuple[str, str]]]],
        selected: set[str] | None = None,
    ) -> None:
        """``groups`` pairs an optional heading with its chips, and each
        chip pairs its key with its text, such as ("pasta", "pasta 3")."""
        self.groups = groups
        self.selected = set(selected or ())
        self.redraw()

    def redraw(self) -> None:
        scaling = widget_scaling(self)
        set_font(self.font, size=-round(11 * scaling))
        set_font(self.heading_font, size=-round(10 * scaling))
        width = round(self.unscaled_width * scaling)
        chip_height = round(self.CHIP_HEIGHT * scaling)
        gap = round(self.GAP * scaling)
        padding = round(self.PADDING * scaling)
        self.configure(bg=color(BACKGROUND), width=width)
        self.delete("all")
        y = 0
        for group_index, (heading, chips) in enumerate(self.groups):
            if group_index:
                y += round(18 * scaling)
            if heading:
                self.create_text(
                    0, y, text=heading.upper(), anchor="nw",
                    font=self.heading_font, fill=color(MUTED),
                )
                y += round(16 * scaling)
            x = 0
            row_top = y + (gap if heading else 0)
            for key, text in chips:
                chip_width = self.font.measure(text) + 2 * padding
                if x and x + chip_width > width:
                    x = 0
                    row_top += chip_height + gap
                on = key in self.selected
                tag = f"chip:{key}"
                self.create_rectangle(
                    x, row_top, x + chip_width - 1, row_top + chip_height,
                    outline=color(INK if on else RULE),
                    fill=color(INK if on else BACKGROUND),
                    tags=(tag, "box"),
                )
                self.create_text(
                    x + padding, row_top + chip_height / 2, text=text, anchor="w",
                    font=self.font, fill=color(BACKGROUND if on else INK_SOFT),
                    tags=(tag,),
                )
                self.tag_bind(tag, "<Button-1>", lambda _event, chosen=key: self.after_idle(self.on_click, chosen))
                self.tag_bind(tag, "<Enter>", lambda _event, chosen=key: self.hover(chosen, True))
                self.tag_bind(tag, "<Leave>", lambda _event, chosen=key: self.hover(chosen, False))
                x += chip_width + gap
            if chips:
                y = row_top + chip_height + 1
        self.configure(height=max(1, y))

    def hover(self, key: str, on: bool) -> None:
        if key in self.selected:
            return
        for item in self.find_withtag(f"chip:{key}"):
            if "box" in self.gettags(item):
                self.itemconfigure(item, fill=color(HOVER if on else BACKGROUND))
        self.configure(cursor="hand2" if on else "")

    def destroy(self) -> None:
        unwatch(self.redraw)
        super().destroy()

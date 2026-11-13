"""Asks before using launcher commands synced from another device.

Commands start programs, so anyone who got into the account could use
them to run something on this computer. The dialog shows exactly what
each new or changed command would run.
"""

from __future__ import annotations

from typing import Any, Callable

import customtkinter

from .constants import BACKGROUND, HOVER, INK, INK_SOFT, MONO_FONT, MUTED
from .launcher import describe_changes, read_commands_file
from .windows import outline_width, prepare_window

# Longer change lists are cut short, with a count of what's left.
MAX_LINES = 16


def mono(size: int, weight: str = "normal") -> customtkinter.CTkFont:
    return customtkinter.CTkFont(family=MONO_FONT, size=size, weight=weight)


class CommandsDialog(customtkinter.CTkToplevel):
    """``on_answer`` gets True (use them), False (keep mine) or None (the
    window was closed: ask again next launch)."""

    def __init__(
        self,
        parent: customtkinter.CTkToplevel,
        offered: dict[str, Any],
        on_answer: Callable[[bool | None], None],
    ) -> None:
        super().__init__(parent)
        self.on_answer = on_answer
        self.title("Launcher commands changed")
        self.resizable(False, False)
        self.transient(parent)
        self.configure(fg_color=BACKGROUND)
        prepare_window(self)
        self.protocol("WM_DELETE_WINDOW", lambda: self.answer(None))
        # Grab once the window is mapped; grabbing earlier fails on Linux.
        self.after(100, self.grab_set)

        card = customtkinter.CTkFrame(
            self,
            fg_color=BACKGROUND,
            border_color=INK,
            border_width=outline_width(parent),
            corner_radius=0,
        )
        card.pack(fill="both", expand=True, padx=8, pady=8)
        customtkinter.CTkLabel(
            card,
            text="launcher commands changed",
            text_color=INK,
            font=mono(15, "bold"),
        ).pack(anchor="w", padx=18, pady=(16, 4))
        customtkinter.CTkLabel(
            card,
            text=(
                "another device signed in to your account changed them. "
                "commands start programs, so only use these if you made "
                "the change."
            ),
            text_color=INK_SOFT,
            justify="left",
            wraplength=440,
            font=mono(10),
        ).pack(anchor="w", padx=18)

        lines = describe_changes(read_commands_file(), offered["data"])
        if len(lines) > MAX_LINES:
            hidden = len(lines) - MAX_LINES + 1
            lines = [*lines[:MAX_LINES - 1], f"... and {hidden} more lines"]
        customtkinter.CTkLabel(
            card,
            text="\n".join(lines),
            text_color=INK,
            justify="left",
            anchor="w",
            wraplength=440,
            font=mono(10),
        ).pack(anchor="w", fill="x", padx=18, pady=(12, 4))
        customtkinter.CTkLabel(
            card,
            text="keeping yours asks again only if they change again.",
            text_color=MUTED,
            justify="left",
            wraplength=440,
            font=mono(9),
        ).pack(anchor="w", padx=18, pady=(4, 0))

        buttons = customtkinter.CTkFrame(card, fg_color="transparent")
        buttons.pack(fill="x", padx=18, pady=(14, 16))
        customtkinter.CTkButton(
            buttons,
            text="use these",
            width=110,
            height=32,
            corner_radius=0,
            fg_color="transparent",
            hover_color=HOVER,
            border_color=INK,
            border_width=outline_width(parent),
            text_color=INK,
            font=mono(11, "bold"),
            command=lambda: self.answer(True),
        ).pack(side="right")
        # The safe choice is the solid one, and the default.
        keep = customtkinter.CTkButton(
            buttons,
            text="keep mine",
            width=110,
            height=32,
            corner_radius=0,
            fg_color=INK,
            hover_color=INK_SOFT,
            text_color=BACKGROUND,
            font=mono(11, "bold"),
            command=lambda: self.answer(False),
        )
        keep.pack(side="right", padx=(0, 6))
        self.bind("<Escape>", lambda _event: self.answer(None))

    def answer(self, accepted: bool | None) -> None:
        self.destroy()
        self.on_answer(accepted)

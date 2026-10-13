from __future__ import annotations

import customtkinter

from .constants import (
    APP_AUTHOR,
    APP_EMAIL,
    APP_NAME,
    APP_REPOSITORY,
    APP_VERSION,
    BACKGROUND,
    INK,
    INK_SOFT,
    MONO_FONT,
    MUTED,
)
from .windows import outline_width, prepare_window


def mono(size: int, weight: str = "normal") -> customtkinter.CTkFont:
    return customtkinter.CTkFont(family=MONO_FONT, size=size, weight=weight)


def show_about(parent: customtkinter.CTkToplevel) -> None:
    dialog = customtkinter.CTkToplevel(parent)
    dialog.title(f"About {APP_NAME}")
    dialog.geometry("330x285")
    dialog.resizable(False, False)
    dialog.transient(parent)
    dialog.configure(fg_color=BACKGROUND)
    prepare_window(dialog)
    # Grab once the window is mapped; grabbing earlier fails on Linux.
    dialog.after(100, dialog.grab_set)

    card = customtkinter.CTkFrame(
        dialog,
        fg_color=BACKGROUND,
        border_color=INK,
        border_width=outline_width(parent),
        corner_radius=0,
    )
    card.pack(fill="both", expand=True, padx=8, pady=8)
    customtkinter.CTkLabel(
        card,
        text=APP_NAME,
        text_color=INK,
        font=mono(22, "bold"),
    ).pack(pady=(22, 2))
    customtkinter.CTkLabel(
        card,
        text=f"version {APP_VERSION}",
        text_color=MUTED,
        font=mono(11),
    ).pack()
    customtkinter.CTkLabel(
        card,
        text=(
            f"made with love by {APP_AUTHOR}\n"
            f"{APP_EMAIL}\n\n"
            f"{APP_REPOSITORY}"
        ),
        text_color=INK_SOFT,
        justify="center",
        wraplength=285,
        font=mono(10),
    ).pack(pady=(15, 8))
    customtkinter.CTkButton(
        card,
        text="Close",
        width=100,
        height=32,
        corner_radius=0,
        fg_color=INK,
        hover_color=INK_SOFT,
        text_color=BACKGROUND,
        font=mono(11),
        command=dialog.destroy,
    ).pack(pady=(0, 14))

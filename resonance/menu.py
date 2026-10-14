from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from typing import Callable

import customtkinter

from .constants import (
    APP_NAME,
    APP_SIZES,
    BACKGROUND,
    HOVER,
    INK,
    INK_SOFT,
    MONO_FONT,
    MUTED,
)
from .windows import outline_width

# Placed in a menu's item list to insert the size picker row.
SIZE_ROW = "size"
MENU_WIDTH = 300


@dataclass(frozen=True)
class MenuItem:
    label: str
    command: Callable[[], None]
    text_color: str = INK_SOFT
    enabled: bool = True


def mono(size: int, weight: str = "normal") -> customtkinter.CTkFont:
    return customtkinter.CTkFont(family=MONO_FONT, size=size, weight=weight)


def build_context_menu(
    owner: customtkinter.CTkToplevel,
    x: int,
    y: int,
    items: list[MenuItem | str],
    size_name: str,
    on_size: Callable[[str], None],
    on_close: Callable[[], None],
) -> customtkinter.CTkToplevel:
    """Pop up a borderless menu at screen position (x, y).

    Choosing anything calls ``on_close`` first, so the caller can drop
    its reference to the menu before the command runs.
    """
    menu = customtkinter.CTkToplevel(owner)
    # Hidden while it's built and measured, so it never flashes in the
    # wrong place.
    menu.withdraw()
    menu.overrideredirect(True)
    menu.attributes("-topmost", True)
    menu.configure(fg_color=BACKGROUND)
    menu.bind("<Escape>", lambda _event: on_close())

    frame = customtkinter.CTkFrame(
        menu,
        fg_color=BACKGROUND,
        border_color=INK,
        border_width=outline_width(owner),
        corner_radius=0,
    )
    frame.pack(fill="both", expand=True)
    # Sets the menu's minimum width; padded so it can't cover the border.
    customtkinter.CTkFrame(
        frame,
        width=MENU_WIDTH,
        height=1,
        fg_color="transparent",
    ).pack(padx=8, pady=(6, 0))
    customtkinter.CTkLabel(
        frame,
        text=f"  {APP_NAME}",
        anchor="w",
        text_color=INK,
        font=mono(11, "bold"),
    ).pack(fill="x", padx=8, pady=(4, 5))

    def choose(command: Callable[[], None]) -> None:
        on_close()
        command()

    for item in items:
        if item == SIZE_ROW:
            add_size_row(frame, size_name, lambda name: choose(lambda: on_size(name)))
            continue
        assert isinstance(item, MenuItem)
        customtkinter.CTkButton(
            frame,
            text=item.label,
            command=lambda chosen=item: choose(chosen.command),
            state="normal" if item.enabled else "disabled",
            anchor="w",
            height=32,
            corner_radius=0,
            fg_color="transparent",
            hover_color=HOVER,
            text_color=item.text_color,
            font=mono(11),
        ).pack(fill="x", padx=8, pady=2)
    customtkinter.CTkFrame(
        frame,
        width=MENU_WIDTH,
        height=4,
        fg_color="transparent",
    ).pack(padx=8, pady=(0, 6))

    # Position only (the menu sizes itself to its contents), in raw screen
    # pixels, which CTk doesn't scale.
    tk.Wm.wm_geometry(menu, "+{}+{}".format(*fit_on_screen(menu, x, y)))
    menu.deiconify()
    close_when_focus_leaves(menu, on_close)
    menu.focus_force()
    return menu


def fit_on_screen(menu: tk.Misc, x: int, y: int) -> tuple[int, int]:
    """Open up and/or left of the pointer when there's no room below or to
    the right of it, so the whole menu stays on screen."""
    menu.update_idletasks()
    width, height = menu.winfo_reqwidth(), menu.winfo_reqheight()
    screen_width, screen_height = menu.winfo_screenwidth(), menu.winfo_screenheight()
    if x + width > screen_width:
        x -= width
    if y + height > screen_height:
        y -= height
    return (
        max(0, min(x, screen_width - width)),
        max(0, min(y, screen_height - height)),
    )


def close_when_focus_leaves(menu: tk.Misc, on_close: Callable[[], None]) -> None:
    """Close the menu when the user clicks anywhere else, including other
    apps. Only armed once the menu has actually been focused, so it can't
    close the moment it opens. Clicks on t1ld3's own windows are also
    caught by their <Button-1> bindings, for desktops that never give a
    borderless window focus."""
    armed = False

    def focus_in(_event: tk.Event[tk.Misc]) -> None:
        nonlocal armed
        armed = True

    def focus_out(_event: tk.Event[tk.Misc]) -> None:
        # Let the focus settle, then check where it went.
        if armed:
            menu.after(50, close_if_unfocused)

    def close_if_unfocused() -> None:
        if not menu.winfo_exists():
            return
        try:
            focused = menu.focus_get()
        except (KeyError, tk.TclError):
            focused = None
        if focused is None or focused.winfo_toplevel() is not menu:
            on_close()

    menu.bind("<FocusIn>", focus_in)
    menu.bind("<FocusOut>", focus_out)


def add_size_row(
    parent: customtkinter.CTkFrame,
    size_name: str,
    on_size: Callable[[str], None],
) -> None:
    row = customtkinter.CTkFrame(parent, fg_color="transparent")
    row.pack(fill="x", padx=8, pady=2)
    customtkinter.CTkLabel(
        row,
        text="  Size",
        anchor="w",
        text_color=INK_SOFT,
        font=mono(11),
    ).pack(side="left", fill="x", expand=True)
    for name in APP_SIZES:
        selected = name == size_name
        customtkinter.CTkButton(
            row,
            text=name,
            width=29,
            height=24,
            corner_radius=0,
            fg_color=INK if selected else "transparent",
            hover_color=INK_SOFT if selected else HOVER,
            text_color=BACKGROUND if selected else MUTED,
            font=mono(10, "bold"),
            command=lambda chosen=name: on_size(chosen),
        ).pack(side="left", padx=1)

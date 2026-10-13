from __future__ import annotations

import ctypes
import os
import tkinter as tk
from pathlib import Path

import customtkinter

ICON_PATH: Path = Path(__file__).resolve().parents[1] / "assets" / "icon.ico"


def prepare_window(window: tk.Wm | tk.Misc) -> None:
    """Give a top-level window the app icon and its own taskbar entry."""
    if os.name != "nt":
        return

    window.iconbitmap(str(ICON_PATH))
    # CTkToplevel swaps in its default icon shortly after creation.
    window.after(250, lambda: window.iconbitmap(str(ICON_PATH)))
    window.after(100, configure_taskbar_presence, window)
    window.after(500, configure_taskbar_presence, window)


def configure_taskbar_presence(window: tk.Misc) -> None:
    # Remove the tool-window style so Windows groups the app in the taskbar.
    hwnd: int = window.winfo_id()
    get_window_long = ctypes.windll.user32.GetWindowLongW
    set_window_long = ctypes.windll.user32.SetWindowLongW
    set_window_pos = ctypes.windll.user32.SetWindowPos
    ex_style = get_window_long(hwnd, -20)
    app_window = 0x00040000
    tool_window = 0x00000080
    set_window_long(
        hwnd,
        -20,
        (ex_style | app_window) & ~tool_window,
    )
    set_window_pos(
        hwnd,
        0,
        0,
        0,
        0,
        0x0001 | 0x0002 | 0x0020 | 0x0040,
    )


def outline_width(widget: tk.Misc) -> int:
    # CTk scales border widths, so a 1px outline vanishes below 100%.
    scaling = customtkinter.ScalingTracker.get_widget_scaling(widget)
    return 2 if scaling < 1 else 1


def add_rule(
    parent: tk.Misc,
    color: str,
    padx: int = 0,
    pady: tuple[int, int] = (0, 0),
) -> tk.Frame:
    """Pack a 1px horizontal line; CTkFrame draws nothing that thin."""
    scaling = customtkinter.ScalingTracker.get_widget_scaling(parent)
    line = tk.Frame(parent, height=1, bg=color, bd=0, highlightthickness=0)
    line.pack(
        fill="x",
        padx=round(padx * scaling),
        pady=(round(pady[0] * scaling), round(pady[1] * scaling)),
    )
    return line


def cancel_pending_after(widget: tk.Misc) -> None:
    """Cancel a widget's scheduled callbacks before it is destroyed.

    Polling loops reschedule themselves with ``after``; without this, Tk
    fires them against the destroyed widget and prints errors.
    """
    owned = set(widget._tclCommands or ())
    for after_id in widget.tk.splitlist(widget.tk.call("after", "info")):
        try:
            script = widget.tk.splitlist(
                widget.tk.call("after", "info", after_id)
            )[0]
        except tk.TclError:
            continue
        if script in owned:
            widget.after_cancel(after_id)

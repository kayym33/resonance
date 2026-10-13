from __future__ import annotations

import json
import os
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from .constants import BACKGROUND, INK, INK_SOFT, MONO_FONT

CONFIG_PATH: Path = (
    Path(os.environ.get("LOCALAPPDATA", Path.home()))
    / "Resonance"
    / "spotify.json"
)


def load_config() -> dict[str, str]:
    if not CONFIG_PATH.exists():
        return {}

    with CONFIG_PATH.open(encoding="utf-8") as config_file:
        config: object = json.load(config_file)

    if not isinstance(config, dict):
        return {}

    return {
        key: value
        for key, value in config.items()
        if key in {"client_id", "client_secret", "redirect_uri"}
        and isinstance(value, str)
    }


def save_config(config: dict[str, str]) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CONFIG_PATH.open("w", encoding="utf-8") as config_file:
        json.dump(config, config_file, indent=2)


def setup_spotify() -> bool:
    environment_config: dict[str, str] = {
        "client_id": os.environ.get("SPOTIPY_CLIENT_ID", ""),
        "client_secret": os.environ.get("SPOTIPY_CLIENT_SECRET", ""),
        "redirect_uri": os.environ.get(
            "SPOTIPY_REDIRECT_URI",
            "http://127.0.0.1:8888/callback",
        ),
    }
    if environment_config["client_id"] and environment_config["client_secret"]:
        return True

    config: dict[str, str] = load_config()
    if all(config.get(key) for key in ("client_id", "client_secret")):
        os.environ.update(
            {
                "SPOTIPY_CLIENT_ID": config["client_id"],
                "SPOTIPY_CLIENT_SECRET": config["client_secret"],
                "SPOTIPY_REDIRECT_URI": config.get(
                    "redirect_uri",
                    "http://127.0.0.1:8888/callback",
                ),
            }
        )
        return True

    window = tk.Tk()
    window.title("Resonance setup")
    window.resizable(False, False)
    window.configure(bg=BACKGROUND)
    label_style: dict[str, object] = {
        "bg": BACKGROUND,
        "fg": INK,
        "font": (MONO_FONT, 10),
    }

    fields: dict[str, tk.Entry] = {}
    labels: tuple[tuple[str, str, str], ...] = (
        ("client_id", "Spotify Client ID", ""),
        ("client_secret", "Spotify Client Secret", ""),
        (
            "redirect_uri",
            "Redirect URI",
            "http://127.0.0.1:8888/callback",
        ),
    )

    tk.Label(
        window,
        text="Enter your Spotify Developer credentials.",
        padx=20,
        pady=12,
        **label_style,
    ).grid(row=0, column=0, columnspan=2)

    for row, (key, label, default) in enumerate(labels, start=1):
        tk.Label(window, text=label, **label_style).grid(
            row=row,
            column=0,
            padx=(20, 8),
            pady=5,
            sticky="e",
        )
        entry = tk.Entry(
            window,
            width=38,
            show="*" if key == "client_secret" else "",
            bg="#F0F0E8",
            fg=INK,
            insertbackground=INK,
            relief="flat",
            highlightthickness=1,
            highlightbackground=INK_SOFT,
            highlightcolor=INK,
            font=(MONO_FONT, 10),
        )
        entry.insert(0, config.get(key, default))
        entry.grid(row=row, column=1, padx=(0, 20), pady=5)
        fields[key] = entry

    result: dict[str, bool] = {"saved": False}

    def submit() -> None:
        values: dict[str, str] = {
            key: entry.get().strip() for key, entry in fields.items()
        }
        if not values["client_id"] or not values["client_secret"]:
            messagebox.showerror(
                "Missing credentials",
                "Client ID and Client Secret are required.",
                parent=window,
            )
            return

        save_config(values)
        os.environ.update(
            {
                "SPOTIPY_CLIENT_ID": values["client_id"],
                "SPOTIPY_CLIENT_SECRET": values["client_secret"],
                "SPOTIPY_REDIRECT_URI": values["redirect_uri"],
            }
        )
        result["saved"] = True
        window.destroy()

    tk.Button(
        window,
        text="Save and continue",
        command=submit,
        bg=INK,
        fg=BACKGROUND,
        activebackground=INK_SOFT,
        activeforeground=BACKGROUND,
        relief="flat",
        borderwidth=0,
        padx=14,
        pady=6,
        font=(MONO_FONT, 10, "bold"),
    ).grid(
        row=4,
        column=0,
        columnspan=2,
        pady=(12, 20),
    )
    window.protocol("WM_DELETE_WINDOW", window.destroy)
    window.mainloop()
    return result["saved"]

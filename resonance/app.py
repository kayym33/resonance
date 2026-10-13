from __future__ import annotations

import ctypes
import os
import tkinter as tk
from concurrent.futures import Future, ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.request import urlopen

import customtkinter
from PIL import Image

from .ascii_art import render_ascii_art
from .backend import (
    SPOTIFY_REFRESH_TIME,
    get_current_song,
    next_song,
    previous_song,
    toggle_playback,
)
from .hub import HubWindow
from .player import PlayerWindow
from .windows import prepare_window


class ResonanceApp(customtkinter.CTk):
    """Hidden root that owns Spotify state and the hub and player windows.

    Tk closes every window when the root goes away, so the root stays
    hidden and the app only quits once both visible windows are closed.
    """

    def __init__(self) -> None:
        super().__init__()
        self.withdraw()
        self.title("Resonance")
        prepare_window(self)
        self.worker: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=2)
        self.song: dict[str, Any] | None = None
        self.song_request_active: bool = False
        self.album_art_url: str | None = None
        self.album_art_image: Image.Image = render_ascii_art(None)
        self.hub: HubWindow | None = None
        self.player: PlayerWindow | None = None

        self.open_hub()
        self.poll_song()

    def open_hub(self) -> None:
        if self.hub is None:
            self.hub = HubWindow(self)
        else:
            self.hub.deiconify()
        self.hub.lift()
        self.hub.focus_force()

    def open_player(self) -> None:
        if self.player is None:
            self.player = PlayerWindow(self)
        else:
            self.player.deiconify()
        self.player.lift()

    def close_hub(self) -> None:
        if self.hub is not None:
            self.hub.destroy()
            self.hub = None
        self.quit_if_no_windows()

    def close_player(self) -> None:
        if self.player is not None:
            self.player.destroy()
            self.player = None
        self.quit_if_no_windows()

    def quit_if_no_windows(self) -> None:
        if self.hub is None and self.player is None:
            self.quit_app()

    def quit_app(self, _event: tk.Event[tk.Misc] | None = None) -> str:
        self.worker.shutdown(wait=False, cancel_futures=True)
        self.destroy()
        return "break"

    def windows(self) -> list[HubWindow | PlayerWindow]:
        return [window for window in (self.hub, self.player) if window]

    def poll_song(self) -> None:
        self.refresh_song()
        self.after(SPOTIFY_REFRESH_TIME * 1000, self.poll_song)

    def refresh_song(self) -> None:
        if self.song_request_active:
            return

        self.song_request_active = True
        future: Future[dict[str, Any]] = self.worker.submit(get_current_song)
        future.add_done_callback(self.song_request_finished)

    def song_request_finished(self, future: Future[dict[str, Any]]) -> None:
        self.after(0, self.apply_song_result, future)

    def apply_song_result(self, future: Future[dict[str, Any]]) -> None:
        self.song_request_active = False
        try:
            song: dict[str, Any] = future.result()
        except Exception:
            for window in self.windows():
                window.show_song_error()
            return

        self.song = song
        for window in self.windows():
            window.show_song(song)
        if song["album_art_url"] != self.album_art_url:
            self.load_album_art(song["album_art_url"])

    def load_album_art(self, image_url: str | None) -> None:
        self.album_art_url = image_url
        if not image_url:
            self.show_album_art(render_ascii_art(None))
            return

        future: Future[Image.Image] = self.worker.submit(
            self.download_album_art,
            image_url,
        )
        future.add_done_callback(
            lambda completed, requested_url=image_url: (
                self.album_art_request_finished(completed, requested_url)
            )
        )

    @staticmethod
    def download_album_art(image_url: str) -> Image.Image:
        with urlopen(image_url, timeout=5) as response:
            image = Image.open(BytesIO(response.read())).convert("RGB")
        return render_ascii_art(image, seed=image_url)

    def album_art_request_finished(
        self,
        future: Future[Image.Image],
        requested_url: str,
    ) -> None:
        self.after(0, self.apply_album_art, future, requested_url)

    def apply_album_art(
        self,
        future: Future[Image.Image],
        requested_url: str,
    ) -> None:
        if requested_url != self.album_art_url:
            return

        try:
            image: Image.Image = future.result()
        except Exception:
            image = render_ascii_art(None)
        self.show_album_art(image)

    def show_album_art(self, image: Image.Image) -> None:
        self.album_art_image = image
        for window in self.windows():
            window.set_album_art(image)

    def toggle_playback(self) -> None:
        self.worker.submit(toggle_playback)
        self.after(250, self.refresh_song)

    def previous_song(self) -> None:
        self.worker.submit(previous_song)
        self.after(250, self.refresh_song)

    def next_song(self) -> None:
        self.worker.submit(next_song)
        self.after(250, self.refresh_song)

    def run(self) -> None:
        self.mainloop()


def create_app() -> ResonanceApp:
    customtkinter.set_appearance_mode("light")
    theme_path = (
        Path(__file__).resolve().parents[1] / "assets" / "terminal_theme.json"
    )
    customtkinter.set_default_color_theme(str(theme_path))
    if os.name == "nt":
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "resonance.app"
        )
    return ResonanceApp()

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import time
import tkinter as tk
import webbrowser
import ctypes
import json
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from io import BytesIO
from typing import Any
from urllib.request import Request, urlopen

import customtkinter
from PIL import Image
from .backend import (
    REFRESH_TIME,
    SPOTIFY_REFRESH_TIME,
    get_current_song,
    get_time,
    next_song,
    previous_song,
    toggle_playback,
)

QUOTES_PATH: Path = Path(__file__).resolve().parents[1] / "assets" / "quotes.json"
APP_VERSION = "0.1.0"
GITHUB_RELEASES_API = (
    "https://api.github.com/repos/kayym33/resonance/releases/latest"
)
APP_SIZES: dict[str, tuple[str, float]] = {
    "Small": ("240x320", 0.8),
    "Default": ("300x400", 1.0),
    "Large": ("375x500", 1.25),
}


def load_quotes() -> tuple[str, ...]:
    with QUOTES_PATH.open(encoding="utf-8") as quotes_file:
        quotes: Any = json.load(quotes_file)

    if not isinstance(quotes, list) or not all(
        isinstance(quote, str) for quote in quotes
    ):
        raise ValueError("assets/quotes.json must contain a list of strings")

    return tuple(quotes)


QUOTES: tuple[str, ...] = load_quotes()


class ResonanceApp(customtkinter.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.size_var: tk.StringVar = tk.StringVar(value="Default")
        self.geometry(APP_SIZES["Default"][0])
        self.resizable(False, False)
        self.title("Resonance")
        self.attributes("-topmost", True)
        self.configure(fg_color="#FFF1F5")
        self.bind("<Map>", self.restore_topmost)
        self.bind_all("<Button-3>", self.show_context_menu)
        self.bind_all("<Control-q>", self.close_app)
        self.bind_all("<Escape>", self.close_app)
        if os.name == "nt":
            icon_path: Path = (
                Path(__file__).resolve().parents[1] / "assets" / "icon.ico"
            )
            self.iconbitmap(str(icon_path))
        self.drag_start_x: int = 0
        self.drag_start_y: int = 0
        self.album_art_url: str | None = None
        self.album_art: customtkinter.CTkImage | None = None
        self.progress_ms: int = 0
        self.duration_ms: int = 0
        self.is_playing: bool = False
        self.progress_updated_at: float = time.monotonic()
        self.always_on_top: bool = True
        self.always_on_top_var: tk.BooleanVar = tk.BooleanVar(value=True)
        self.worker: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=2)
        self.song_request_active: bool = False
        self.album_art_request_active: bool = False
        self.quote_index: int = 0
        self.context_menu: tk.Menu = tk.Menu(self, tearoff=False)
        self.context_menu.add_command(
            label="Open Spotify",
            command=self.open_spotify,
        )
        self.context_menu.add_separator()
        self.context_menu.add_checkbutton(
            label="Always on top",
            variable=self.always_on_top_var,
            command=self.toggle_always_on_top,
        )
        self.size_menu: tk.Menu = tk.Menu(self.context_menu, tearoff=False)
        for size_name in APP_SIZES:
            self.size_menu.add_radiobutton(
                label=size_name,
                variable=self.size_var,
                value=size_name,
                command=lambda name=size_name: self.set_app_size(name),
            )
        self.context_menu.add_cascade(label="Size", menu=self.size_menu)
        self.context_menu.add_command(
            label="Refresh song",
            command=self.refresh_song,
        )
        self.context_menu.add_command(
            label="Check for updates",
            command=self.check_for_updates,
        )
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Exit", command=self.close_app)

        self.time_label: customtkinter.CTkLabel = customtkinter.CTkLabel(
            self,
            text="",
            font=customtkinter.CTkFont(
                family="Segoe UI",
                size=34,
                weight="normal",
            ),
            text_color="#B84F6B",
            anchor="center",
        )
        self.time_label.pack(fill="x", padx=20, pady=(16, 10))

        self.user_label: customtkinter.CTkLabel = customtkinter.CTkLabel(
            self,
            text="",
            font=customtkinter.CTkFont(
                family="Segoe UI",
                size=10,
                slant="italic",
            ),
            text_color="#9A5B6D",
            anchor="center",
        )
        self.user_label.pack(fill="x", pady=(0, 8))

        self.album_art_frame: customtkinter.CTkFrame = customtkinter.CTkFrame(
            self,
            width=108,
            height=108,
            corner_radius=4,
            fg_color="#FFFFFF",
            border_width=0,
        )
        self.album_art_frame.pack(pady=(0, 12))
        self.album_art_frame.pack_propagate(False)

        self.album_art_label: customtkinter.CTkLabel = customtkinter.CTkLabel(
            self.album_art_frame,
            text="",
            width=100,
            height=100,
            corner_radius=2,
        )
        self.album_art_label.pack(expand=True)

        self.track_frame: customtkinter.CTkFrame = customtkinter.CTkFrame(
            self,
            fg_color="transparent",
            corner_radius=0,
            border_width=0,
        )
        self.track_frame.pack(fill="x", padx=20, pady=(0, 10))

        self.track_text_frame: customtkinter.CTkFrame = customtkinter.CTkFrame(
            self.track_frame,
            fg_color="transparent",
        )
        self.track_text_frame.pack(fill="x", expand=True)

        self.song_label: customtkinter.CTkLabel = customtkinter.CTkLabel(
            self.track_text_frame,
            text="Checking Spotify...",
            font=customtkinter.CTkFont(family="Arial", size=18, weight="bold"),
            text_color="#6F3044",
            anchor="center",
        )
        self.song_label.pack(fill="x")

        self.artist_label: customtkinter.CTkLabel = customtkinter.CTkLabel(
            self.track_text_frame,
            text="",
            font=customtkinter.CTkFont(family="Arial", size=13),
            text_color="#9A5B6D",
            anchor="center",
        )
        self.artist_label.pack(fill="x", pady=(3, 0))

        self.track_meta_label: customtkinter.CTkLabel = customtkinter.CTkLabel(
            self.track_text_frame,
            text="",
            font=customtkinter.CTkFont(family="Arial", size=10),
            text_color="#B07182",
            anchor="center",
        )
        self.track_meta_label.pack(fill="x", pady=(2, 0))

        self.progress_frame: customtkinter.CTkFrame = customtkinter.CTkFrame(
            self.track_text_frame,
            fg_color="transparent",
        )
        self.progress_frame.pack(fill="x", pady=(10, 0))

        self.progress_bar: customtkinter.CTkProgressBar = (
            customtkinter.CTkProgressBar(
                self.progress_frame,
                height=5,
                corner_radius=2,
                progress_color="#E05A7A",
                fg_color="#F0B1C0",
            )
        )
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x")

        self.progress_label: customtkinter.CTkLabel = customtkinter.CTkLabel(
            self.progress_frame,
            text="0:00 / 0:00",
            font=customtkinter.CTkFont(family="Arial", size=10),
            text_color="#9A5B6D",
            anchor="e",
        )
        self.progress_label.pack(fill="x", pady=(2, 0))

        self.controls_frame: customtkinter.CTkFrame = customtkinter.CTkFrame(
            self,
            fg_color="transparent",
        )
        self.controls_frame.pack(fill="x", padx=16, pady=(0, 14))

        self.previous_button: customtkinter.CTkButton = customtkinter.CTkButton(
            self.controls_frame,
            text="⏮",
            width=52,
            height=32,
            corner_radius=6,
            fg_color="#E58AA0",
            hover_color="#D8758F",
            font=customtkinter.CTkFont(size=14),
            command=self.previous_song,
        )
        self.previous_button.pack(side="left", expand=True, padx=5)

        self.play_pause_button: customtkinter.CTkButton = customtkinter.CTkButton(
            self.controls_frame,
            text="▶",
            width=58,
            height=34,
            corner_radius=6,
            fg_color="#D8758F",
            hover_color="#C96B86",
            font=customtkinter.CTkFont(size=15, weight="bold"),
            command=self.toggle_playback,
        )
        self.play_pause_button.pack(side="left", expand=True, padx=5)

        self.next_button: customtkinter.CTkButton = customtkinter.CTkButton(
            self.controls_frame,
            text="⏭",
            width=52,
            height=32,
            corner_radius=6,
            fg_color="#E58AA0",
            hover_color="#D8758F",
            font=customtkinter.CTkFont(size=14),
            command=self.next_song,
        )
        self.next_button.pack(side="left", expand=True, padx=5)

        self.update_time()
        self.update_quote()
        self.update_song()
        self.update_progress()
        self.after(100, self.configure_taskbar_presence)
        self.after(500, self.configure_taskbar_presence)

    def update_time(self) -> None:
        self.time_label.configure(text=get_time())
        self.after(REFRESH_TIME * 1000, self.update_time)

    def update_quote(self) -> None:
        self.user_label.configure(text=QUOTES[self.quote_index])
        self.quote_index = (self.quote_index + 1) % len(QUOTES)
        self.after(30_000, self.update_quote)

    def configure_taskbar_presence(self) -> None:
        if os.name != "nt":
            return

        # Remove the tool-window style so Windows groups Resonance in the taskbar.
        hwnd: int = self.winfo_id()
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

    def start_window_drag(self, event: tk.Event[tk.Misc]) -> None:
        self.drag_start_x = event.x_root - self.winfo_x()
        self.drag_start_y = event.y_root - self.winfo_y()

    def minimize_window(self) -> None:
        self.always_on_top = False
        self.always_on_top_var.set(False)
        self.attributes("-topmost", False)
        self.iconify()

    def close_app(self, _event: tk.Event[tk.Misc] | None = None) -> str:
        self.worker.shutdown(wait=False, cancel_futures=True)
        self.destroy()
        return "break"

    def restore_topmost(self, _event: tk.Event[tk.Misc] | None = None) -> None:
        if self.always_on_top:
            self.attributes("-topmost", True)

    def drag_window(self, event: tk.Event[tk.Misc]) -> None:
        x: int = event.x_root - self.drag_start_x
        y: int = event.y_root - self.drag_start_y
        self.geometry(f"+{x}+{y}")

    def show_context_menu(self, event: tk.Event[tk.Misc]) -> None:
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def open_spotify(self) -> None:
        if not webbrowser.open("spotify:"):
            webbrowser.open("https://open.spotify.com/")

    def toggle_always_on_top(self) -> None:
        self.always_on_top = self.always_on_top_var.get()
        self.attributes("-topmost", self.always_on_top)

    def set_app_size(self, size_name: str) -> None:
        size = APP_SIZES.get(size_name)
        if size is None:
            raise ValueError(f"Unknown app size: {size_name}")

        geometry, scaling = size
        customtkinter.set_widget_scaling(scaling)
        customtkinter.set_window_scaling(scaling)
        self.geometry(geometry)

    def refresh_song(self) -> None:
        self.update_song()

    @staticmethod
    def parse_version(version: str) -> tuple[int, ...]:
        numbers = re.findall(r"\d+", version.lstrip("v"))
        return tuple(int(number) for number in numbers) or (0,)

    def check_for_updates(self) -> None:
        if os.name != "nt" or not getattr(sys, "frozen", False):
            messagebox.showinfo(
                "Updates",
                "Automatic updates are available for the Windows executable "
                "distributed through GitHub Releases.",
                parent=self,
            )
            return

        self.context_menu.entryconfigure(
            "Check for updates",
            state=tk.DISABLED,
        )
        self.worker.submit(self.find_update).add_done_callback(
            self.update_check_finished
        )

    @staticmethod
    def find_update() -> tuple[str, str] | None:
        request = Request(
            GITHUB_RELEASES_API,
            headers={"Accept": "application/vnd.github+json"},
        )
        with urlopen(request, timeout=10) as response:
            release: Any = json.load(response)

        if not isinstance(release, dict):
            raise ValueError("GitHub returned an invalid release response")

        tag_name = release.get("tag_name")
        assets = release.get("assets")
        if not isinstance(tag_name, str) or not isinstance(assets, list):
            raise ValueError("GitHub release is missing version or assets")

        for asset in assets:
            if (
                isinstance(asset, dict)
                and asset.get("name") == "Resonance.exe"
                and isinstance(asset.get("browser_download_url"), str)
            ):
                return tag_name, asset["browser_download_url"]
        raise ValueError("The latest release does not contain Resonance.exe")

    def update_check_finished(
        self,
        future: Future[tuple[str, str] | None],
    ) -> None:
        self.after(0, self.apply_update_check, future)

    def apply_update_check(
        self,
        future: Future[tuple[str, str] | None],
    ) -> None:
        self.context_menu.entryconfigure(
            "Check for updates",
            state=tk.NORMAL,
        )
        try:
            update = future.result()
        except Exception as error:
            messagebox.showerror(
                "Update check failed",
                f"Could not check GitHub Releases:\n{error}",
                parent=self,
            )
            return

        if update is None or self.parse_version(update[0]) <= self.parse_version(
            APP_VERSION
        ):
            messagebox.showinfo(
                "Updates",
                f"Resonance {APP_VERSION} is up to date.",
                parent=self,
            )
            return

        tag_name, download_url = update
        if messagebox.askyesno(
            "Update available",
            f"Resonance {tag_name} is available. Download and install it now?",
            parent=self,
        ):
            self.worker.submit(
                self.download_update,
                download_url,
            ).add_done_callback(self.update_download_finished)

    @staticmethod
    def download_update(download_url: str) -> Path:
        download_path = Path(tempfile.gettempdir()) / "Resonance-update.exe"
        request = Request(
            download_url,
            headers={"Accept": "application/octet-stream"},
        )
        with urlopen(request, timeout=60) as response, download_path.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        return download_path

    def update_download_finished(self, future: Future[Path]) -> None:
        self.after(0, self.apply_downloaded_update, future)

    def apply_downloaded_update(self, future: Future[Path]) -> None:
        try:
            download_path = future.result()
            current_exe = Path(sys.executable).resolve()
            updater_path = Path(tempfile.gettempdir()) / "Resonance-updater.bat"
            updater_path.write_text(
                "@echo off\r\n"
                "timeout /t 2 /nobreak >nul\r\n"
                f'copy /y "{download_path}" "{current_exe}" >nul\r\n'
                f'start "" "{current_exe}"\r\n'
                f'del "%~f0"\r\n',
                encoding="utf-8",
            )
            subprocess.Popen(
                ["cmd", "/c", str(updater_path)],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except Exception as error:
            messagebox.showerror(
                "Update failed",
                f"Could not install the update:\n{error}",
                parent=self,
            )
            return
        self.close_app()

    def update_song(self) -> None:
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
            self.artist_label.configure(text="Spotify unavailable")
            self.after(SPOTIFY_REFRESH_TIME * 1000, self.update_song)
            return

        self.song_label.configure(text=song["title"])
        self.artist_label.configure(text=song["artist"])
        album: str = song["album"]
        device: str = song["device"]
        metadata: str = " • ".join(value for value in (album, device) if value)
        self.track_meta_label.configure(text=metadata)
        self.play_pause_button.configure(
            text="⏸" if song["is_playing"] else "▶"
        )
        duration_ms: int = song["duration_ms"]
        self.progress_ms = song["progress_ms"]
        self.duration_ms = duration_ms
        self.is_playing = song["is_playing"]
        self.progress_updated_at = time.monotonic()

        if song["album_art_url"] != self.album_art_url:
            self.load_album_art(song["album_art_url"])

        self.after(SPOTIFY_REFRESH_TIME * 1000, self.update_song)

    def update_progress(self) -> None:
        progress_ms: int = self.progress_ms
        if self.is_playing:
            elapsed_ms: int = int(
                (time.monotonic() - self.progress_updated_at) * 1000
            )
            progress_ms += elapsed_ms

        progress_ms = min(progress_ms, self.duration_ms) if self.duration_ms else 0
        progress: float = (
            progress_ms / self.duration_ms if self.duration_ms else 0
        )
        self.progress_bar.set(progress)
        self.progress_label.configure(
            text=f"{self.format_time(progress_ms)} / "
            f"{self.format_time(self.duration_ms)}"
        )
        self.after(REFRESH_TIME * 1000, self.update_progress)

    @staticmethod
    def format_time(milliseconds: int) -> str:
        total_seconds: int = milliseconds // 1000
        minutes: int
        seconds: int
        minutes, seconds = divmod(total_seconds, 60)
        return f"{minutes}:{seconds:02d}"

    def load_album_art(self, image_url: str | None) -> None:
        self.album_art_url = image_url
        if not image_url:
            self.album_art = None
            self.album_art_label.configure(image=None, text="")
            return

        if self.album_art_request_active:
            return

        self.album_art_request_active = True
        future: Future[Image.Image] = self.worker.submit(
            self.download_album_art,
            image_url,
        )
        future.add_done_callback(self.album_art_request_finished)

    @staticmethod
    def download_album_art(image_url: str) -> Image.Image:
        with urlopen(image_url, timeout=5) as response:
            return Image.open(BytesIO(response.read())).convert("RGB")

    def album_art_request_finished(self, future: Future[Image.Image]) -> None:
        self.after(0, self.apply_album_art, future)

    def apply_album_art(self, future: Future[Image.Image]) -> None:
        self.album_art_request_active = False
        try:
            image: Image.Image = future.result()
        except Exception:
            self.album_art_label.configure(image=None, text="")
            return

        self.album_art = customtkinter.CTkImage(
            light_image=image,
            dark_image=image,
            size=(100, 100),
        )
        self.album_art_label.configure(image=self.album_art, text="")

    def toggle_playback(self) -> None:
        self.worker.submit(toggle_playback)
        self.after(250, self.update_song)

    def previous_song(self) -> None:
        self.worker.submit(previous_song)
        self.after(250, self.update_song)

    def next_song(self) -> None:
        self.worker.submit(next_song)
        self.after(250, self.update_song)

    def run(self) -> None:
        self.mainloop()


def create_app() -> ResonanceApp:
    customtkinter.set_appearance_mode("light")
    theme_path = Path(__file__).resolve().parents[1] / "assets" / "pink_theme.json"
    customtkinter.set_default_color_theme(str(theme_path))
    if os.name == "nt":
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "resonance.app"
        )
    return ResonanceApp()

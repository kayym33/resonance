from __future__ import annotations

import ctypes
import os
import sys
import tkinter as tk
import webbrowser
from concurrent.futures import Future, ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from tkinter import messagebox
from typing import Any
from urllib.request import urlopen

import customtkinter
from PIL import Image

from . import updater
from .about import show_about
from .account_dialog import AccountDialog
from .ascii_art import render_ascii_art, render_avatar, render_avatar_icon
from .backend import (
    SPOTIFY_REFRESH_TIME,
    get_current_song,
    next_song,
    previous_song,
    toggle_playback,
)
from .constants import APP_NAME, APP_SIZES, APP_VERSION, DEFAULT_SIZE
from .hub import HubWindow
from .instance import listen
from .menu import MenuItem, build_context_menu
from .settings import load_device_setting, save_device_setting
from .sync import SyncEngine
from .user_profile import avatar_source, display_name, profile_data
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
        self.title(APP_NAME)
        prepare_window(self)
        # Spotify, album art, weather, sync and sign-in can all be waiting at
        # once; the first Spotify login holds a worker until it's approved.
        self.worker: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=4)
        self.song: dict[str, Any] | None = None
        self.song_request_active: bool = False
        self.album_art_url: str | None = None
        self.album_art_image: Image.Image = render_ascii_art(None)
        self.hub: HubWindow | None = None
        self.player: PlayerWindow | None = None
        # Size preset from the right-click menu; its zoom is app-wide.
        self.size_name: str = DEFAULT_SIZE
        self.context_menu: customtkinter.CTkToplevel | None = None
        self.update_check_enabled: bool = True
        self.account_dialog: AccountDialog | None = None
        self.avatar_cache: tuple[object, Image.Image, Image.Image] | None = None
        self.sync: SyncEngine = SyncEngine(self)
        self.sync.listeners.append(self.account_changed)
        # Tk's Entry treats Ctrl+A as "go to line start"; make it select all.
        self.bind_class("Entry", "<Control-a>", self.select_all)
        # A second launch of the app asks this copy to show the hub.
        self.instance_server = listen(lambda: self.after(0, self.open_hub))

        self.open_hub()
        self.poll_song()
        if self.sync.session is None and not load_device_setting("account_prompted"):
            self.after(800, self.prompt_for_account)

    def open_hub(self) -> None:
        if self.hub is None:
            self.hub = HubWindow(self)
        else:
            self.hub.deiconify()
            self.hub.focus_launcher()
        self.hub.lift()

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
        if self.instance_server is not None:
            self.instance_server.close()
        self.destroy()
        return "break"

    @staticmethod
    def select_all(event: tk.Event[tk.Entry]) -> str:
        event.widget.select_range(0, "end")
        event.widget.icursor("end")
        return "break"

    # Accounts and sync

    def prompt_for_account(self) -> None:
        """Offer sign-in once per device, on first launch."""
        save_device_setting("account_prompted", True)
        if self.hub is not None and self.sync.session is None:
            self.open_account(self.hub)

    def open_account(self, parent: customtkinter.CTkToplevel) -> None:
        if self.account_dialog is not None and self.account_dialog.winfo_exists():
            self.account_dialog.lift()
            return
        self.account_dialog = AccountDialog(parent, self)

    def account_label(self) -> tuple[str, bool]:
        """Header text for the account button, and whether it's a problem."""
        session = self.sync.session
        if session is None:
            return "sign in", False
        name = display_name() or session.email.split("@")[0]
        marks = {"syncing": "~", "offline": "!", "error": "!"}
        mark = marks.get(self.sync.status, "")
        return f"{name} {mark}".strip(), self.sync.status in ("offline", "error")

    def avatar_images(self) -> tuple[Image.Image, Image.Image]:
        """The profile picture as (large ASCII art, small pixel icon)."""
        session = self.sync.session
        initial = (display_name() or (session.email if session else "") or "~")[:1]
        key = (profile_data().get("avatar"), initial)
        if self.avatar_cache is None or self.avatar_cache[0] != key:
            source = avatar_source()
            self.avatar_cache = (
                key,
                render_avatar(source, initial),
                render_avatar_icon(source, initial),
            )
        return self.avatar_cache[1], self.avatar_cache[2]

    def account_changed(self) -> None:
        if self.hub is not None:
            self.hub.show_account()

    def profile_changed(self) -> None:
        self.account_changed()
        if self.player is not None and self.song is not None:
            self.player.show_song(self.song)

    def data_changed(self, kinds: set[str]) -> None:
        """Synced data changed underneath the UI; refresh what shows it."""
        hub = self.hub
        if hub is not None:
            if "task" in kinds:
                hub.todo_panel.reload()
            if "event" in kinds and hub.calendar_page is not None:
                hub.calendar_page.reload()
            if "setting" in kinds:
                hub.weather_panel.reload()
        if "profile" in kinds:
            self.profile_changed()

    def windows(self) -> list[HubWindow | PlayerWindow]:
        return [window for window in (self.hub, self.player) if window]

    def dialog_parent(
        self,
        preferred: customtkinter.CTkToplevel,
    ) -> tk.Misc:
        """A live window to own a dialog, in case ``preferred`` closed."""
        if preferred.winfo_exists():
            return preferred
        return next(iter(self.windows()), self)

    # Right-click menu, shared by the hub and the player.

    def show_context_menu(
        self,
        owner: customtkinter.CTkToplevel,
        event: tk.Event[tk.Misc],
        items: list[MenuItem | str],
    ) -> None:
        self.close_context_menu()
        self.context_menu = build_context_menu(
            owner,
            event.x_root,
            event.y_root,
            items,
            self.size_name,
            self.set_size,
            self.close_context_menu,
        )

    def close_context_menu(self) -> None:
        menu, self.context_menu = self.context_menu, None
        if menu is not None and menu.winfo_exists():
            menu.destroy()

    def set_size(self, size_name: str) -> None:
        _, scaling = APP_SIZES[size_name]
        self.size_name = size_name
        customtkinter.set_widget_scaling(scaling)
        customtkinter.set_window_scaling(scaling)
        if self.player is not None:
            self.player.apply_size(size_name)
        if self.hub is not None:
            self.hub.refresh_outlines()

    def show_about(self, parent: customtkinter.CTkToplevel) -> None:
        show_about(parent)

    @staticmethod
    def open_spotify() -> None:
        if not webbrowser.open("spotify:"):
            webbrowser.open("https://open.spotify.com/")

    # Self-update (Windows executable only).

    def check_for_updates(self, parent: customtkinter.CTkToplevel) -> None:
        if os.name != "nt" or not getattr(sys, "frozen", False):
            messagebox.showinfo(
                "Updates",
                "Automatic updates are available for the Windows executable "
                "distributed through GitHub Releases.",
                parent=parent,
            )
            return

        self.update_check_enabled = False
        self.worker.submit(updater.find_update).add_done_callback(
            lambda future: self.after(0, self.apply_update_check, future, parent)
        )

    def apply_update_check(
        self,
        future: Future[tuple[str, str] | None],
        parent: customtkinter.CTkToplevel,
    ) -> None:
        self.update_check_enabled = True
        parent = self.dialog_parent(parent)
        try:
            update = future.result()
        except Exception as error:
            messagebox.showerror(
                "Update check failed",
                f"Could not check GitHub Releases:\n{error}",
                parent=parent,
            )
            return

        if update is None or updater.parse_version(
            update[0]
        ) <= updater.parse_version(APP_VERSION):
            messagebox.showinfo(
                "Updates",
                f"{APP_NAME} {APP_VERSION} is up to date.",
                parent=parent,
            )
            return

        tag_name, download_url = update
        if messagebox.askyesno(
            "Update available",
            f"{APP_NAME} {tag_name} is available. Download and install it now?",
            parent=parent,
        ):
            self.worker.submit(
                updater.download_update,
                download_url,
            ).add_done_callback(
                lambda future: self.after(
                    0,
                    self.apply_downloaded_update,
                    future,
                    parent,
                )
            )

    def apply_downloaded_update(
        self,
        future: Future[Path],
        parent: customtkinter.CTkToplevel,
    ) -> None:
        try:
            download_path = future.result()
            updater.install_update(download_path)
        except Exception as error:
            messagebox.showerror(
                "Update failed",
                f"Could not install the update:\n{error}",
                parent=self.dialog_parent(parent),
            )
            return
        self.quit_app()

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
    _, scaling = APP_SIZES[DEFAULT_SIZE]
    customtkinter.set_widget_scaling(scaling)
    customtkinter.set_window_scaling(scaling)
    theme_path = (
        Path(__file__).resolve().parents[1] / "assets" / "terminal_theme.json"
    )
    customtkinter.set_default_color_theme(str(theme_path))
    if os.name == "nt":
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            f"{APP_NAME}.app"
        )
    return ResonanceApp()

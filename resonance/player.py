from __future__ import annotations

import os
import random
import sys
import time
import tkinter as tk
import webbrowser
from concurrent.futures import Future
from pathlib import Path
from tkinter import messagebox
from typing import TYPE_CHECKING, Any

import customtkinter
from PIL import Image
from .backend import (
    REFRESH_TIME,
    get_time,
    seek_playback,
    set_volume,
)
from .ascii_art import drift_noise, noise_line
from .constants import (
    ACCENT,
    ACCENT_DARK,
    ALBUM_ART_SIZE,
    APP_AUTHOR,
    APP_EMAIL,
    APP_NAME,
    APP_REPOSITORY,
    APP_SIZES,
    APP_VERSION,
    BACKGROUND,
    FAINT,
    HOVER,
    INK,
    INK_SOFT,
    MONO_FONT,
    MUTED,
    QUOTES,
    RULE,
    MIN_LOADING_TIME
)
from . import updater
from .windows import cancel_pending_after, outline_width, prepare_window

if TYPE_CHECKING:
    from .app import ResonanceApp


class PlayerWindow(customtkinter.CTkToplevel):
    def __init__(self, app: ResonanceApp) -> None:
        super().__init__(app)
        self.app: ResonanceApp = app
        self.size_var: tk.StringVar = tk.StringVar(value=app.size_name)
        self.current_size_name: str = app.size_name
        self.smallest_size_name: str = next(iter(APP_SIZES))
        self.controls_visible: bool = True
        self.geometry(APP_SIZES[app.size_name][0])
        self.resizable(False, False)
        self.title(APP_NAME)
        self.attributes("-topmost", True)
        self.configure(fg_color=BACKGROUND)
        self.protocol("WM_DELETE_WINDOW", self.close_window)
        self.bind("<Map>", self.restore_topmost)
        self.bind("<Button-3>", self.show_context_menu)
        self.bind("<Motion>", self.handle_pointer_motion)
        self.bind("<Control-q>", self.app.quit_app)
        self.bind("<Escape>", self.close_window)
        prepare_window(self)
        self.drag_start_x: int = 0
        self.drag_start_y: int = 0
        self.album_art: customtkinter.CTkImage | None = None
        self.progress_ms: int = 0
        self.duration_ms: int = 0
        self.seek_after_id: str | None = None
        self.is_playing: bool = False
        self.volume_percent: int = 0
        self.volume_update_active: bool = False
        self.progress_updated_at: float = time.monotonic()
        self.always_on_top: bool = True
        self.always_on_top_var: tk.BooleanVar = tk.BooleanVar(value=True)
        self.loading_visible: bool = True
        self.loading_animation_id: str | None = None
        self.loading_progress_id: str | None = None
        self.loading_progress_value: float = 0.0
        self.loading_started_at: float = time.monotonic()
        self.quote_index: int = 0
        self.context_menu: customtkinter.CTkToplevel | None = None
        self.update_check_enabled: bool = True
        self.noise_rng: random.Random = random.Random()

        self.noise_label: customtkinter.CTkLabel = customtkinter.CTkLabel(
            self,
            text=noise_line(72, self.noise_rng),
            font=customtkinter.CTkFont(family=MONO_FONT, size=8),
            text_color=FAINT,
            height=12,
            anchor="center",
        )
        self.noise_label.pack(fill="x", pady=(6, 0))

        self.time_label: customtkinter.CTkLabel = customtkinter.CTkLabel(
            self,
            text="",
            font=customtkinter.CTkFont(family=MONO_FONT, size=32),
            text_color=INK,
            anchor="center",
        )
        self.time_label.pack(fill="x", padx=20, pady=(2, 6))

        self.user_label: customtkinter.CTkLabel = customtkinter.CTkLabel(
            self,
            text="",
            font=customtkinter.CTkFont(family=MONO_FONT, size=10),
            text_color=MUTED,
            anchor="center",
            wraplength=260,
        )
        self.user_label.pack(fill="x", pady=(0, 8))

        self.album_art_frame: customtkinter.CTkFrame = customtkinter.CTkFrame(
            self,
            width=ALBUM_ART_SIZE + 8,
            height=ALBUM_ART_SIZE + 8,
            corner_radius=0,
            fg_color=BACKGROUND,
            border_width=0,
        )
        self.album_art_frame.pack(pady=(0, 12))
        self.album_art_frame.pack_propagate(False)

        self.album_art_label: customtkinter.CTkLabel = customtkinter.CTkLabel(
            self.album_art_frame,
            text="",
            width=ALBUM_ART_SIZE,
            height=ALBUM_ART_SIZE,
            corner_radius=0,
        )
        self.album_art_label.pack(expand=True)
        self.set_album_art(self.app.album_art_image)

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

        self.title_viewport: customtkinter.CTkFrame = customtkinter.CTkFrame(
            self.track_text_frame,
            fg_color="transparent",
        )
        self.title_viewport.pack(fill="x")

        self.song_label: customtkinter.CTkLabel = customtkinter.CTkLabel(
            self.title_viewport,
            text="Checking Spotify...",
            font=customtkinter.CTkFont(family=MONO_FONT, size=16, weight="bold"),
            text_color=INK,
            anchor="center",
            justify="center",
            wraplength=260,
        )
        self.song_label.pack(fill="x")

        self.artist_label: customtkinter.CTkLabel = customtkinter.CTkLabel(
            self.track_text_frame,
            text="",
            font=customtkinter.CTkFont(family=MONO_FONT, size=12),
            text_color=INK_SOFT,
            anchor="center",
        )
        self.artist_label.pack(fill="x", pady=(3, 0))

        self.track_meta_label: customtkinter.CTkLabel = customtkinter.CTkLabel(
            self.track_text_frame,
            text="",
            font=customtkinter.CTkFont(family=MONO_FONT, size=10),
            text_color=MUTED,
            anchor="center",
        )
        self.track_meta_label.pack(fill="x", pady=(2, 0))

        self.progress_frame: customtkinter.CTkFrame = customtkinter.CTkFrame(
            self.track_text_frame,
            fg_color="transparent",
        )
        self.progress_frame.pack(fill="x", pady=(10, 0))

        self.progress_label: customtkinter.CTkLabel = customtkinter.CTkLabel(
            self.progress_frame,
            text="0:00 / 0:00",
            font=customtkinter.CTkFont(family=MONO_FONT, size=10),
            text_color=MUTED,
            anchor="center",
        )
        self.progress_label.pack(fill="x", pady=(0, 3))

        self.progress_bar: customtkinter.CTkSlider = customtkinter.CTkSlider(
            self.progress_frame,
            from_=0,
            to=1,
            number_of_steps=1000,
            height=10,
            corner_radius=0,
            border_width=0,
            button_length=4,
            button_corner_radius=0,
            progress_color=INK,
            fg_color=RULE,
            button_color=ACCENT,
            button_hover_color=ACCENT_DARK,
            command=self.change_playback_position,
        )
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x")

        self.volume_frame: customtkinter.CTkFrame = customtkinter.CTkFrame(
            self.track_text_frame,
            fg_color="transparent",
        )
        self.volume_frame.pack(fill="x", pady=(8, 0))

        self.volume_label: customtkinter.CTkLabel = customtkinter.CTkLabel(
            self.volume_frame,
            text="vol",
            font=customtkinter.CTkFont(family=MONO_FONT, size=10),
            text_color=MUTED,
            anchor="w",
        )
        self.volume_label.pack(side="left", padx=(0, 8))

        self.volume_slider: customtkinter.CTkSlider = customtkinter.CTkSlider(
            self.volume_frame,
            from_=0,
            to=100,
            number_of_steps=100,
            height=10,
            corner_radius=0,
            border_width=0,
            button_length=4,
            button_corner_radius=0,
            progress_color=INK,
            fg_color=RULE,
            button_color=ACCENT,
            button_hover_color=ACCENT_DARK,
            command=self.change_volume,
        )
        self.volume_slider.set(0)
        self.volume_slider.pack(side="left", fill="x", expand=True)

        self.controls_frame: customtkinter.CTkFrame = customtkinter.CTkFrame(
            self,
            fg_color="transparent",
        )
        self.controls_frame.pack(
            fill="x",
            padx=16,
            pady=(
                (16, 20)
                if self.current_size_name == self.smallest_size_name
                else (10, 14)
            ),
        )

        self.previous_button: customtkinter.CTkButton = customtkinter.CTkButton(
            self.controls_frame,
            text="|<",
            width=70,
            height=44,
            corner_radius=0,
            border_width=outline_width(self),
            border_color=INK,
            fg_color="transparent",
            hover_color=HOVER,
            text_color=INK,
            font=customtkinter.CTkFont(family=MONO_FONT, size=16, weight="bold"),
            command=self.app.previous_song,
        )
        self.previous_button.pack(side="left", expand=True, padx=5)

        self.play_pause_button: customtkinter.CTkButton = customtkinter.CTkButton(
            self.controls_frame,
            text=">",
            width=80,
            height=48,
            corner_radius=0,
            border_width=0,
            fg_color=INK,
            hover_color=INK_SOFT,
            text_color=BACKGROUND,
            font=customtkinter.CTkFont(family=MONO_FONT, size=18, weight="bold"),
            command=self.app.toggle_playback,
        )
        self.play_pause_button.pack(side="left", expand=True, padx=5)

        self.next_button: customtkinter.CTkButton = customtkinter.CTkButton(
            self.controls_frame,
            text=">|",
            width=70,
            height=44,
            corner_radius=0,
            border_width=outline_width(self),
            border_color=INK,
            fg_color="transparent",
            hover_color=HOVER,
            text_color=INK,
            font=customtkinter.CTkFont(family=MONO_FONT, size=16, weight="bold"),
            command=self.app.next_song,
        )
        self.next_button.pack(side="left", expand=True, padx=5)

        self.loading_frame: customtkinter.CTkFrame = customtkinter.CTkFrame(
            self,
            fg_color=BACKGROUND,
            corner_radius=0,
        )
        self.loading_frame.place(
            relx=0,
            rely=0,
            relwidth=1,
            relheight=1,
        )
        self.loading_title: customtkinter.CTkLabel = customtkinter.CTkLabel(
            self.loading_frame,
            text="Connecting to Spotify...",
            font=customtkinter.CTkFont(family=MONO_FONT, size=17, weight="bold"),
            text_color=INK,
        )
        self.loading_title.place(relx=0.5, rely=0.46, anchor="center")
        self.loading_status: customtkinter.CTkLabel = customtkinter.CTkLabel(
            self.loading_frame,
            text="Just a moment ♡",
            font=customtkinter.CTkFont(family=MONO_FONT, size=11),
            text_color=MUTED,
        )
        self.loading_status.place(relx=0.5, rely=0.54, anchor="center")
        self.loading_progress: customtkinter.CTkProgressBar = (
            customtkinter.CTkProgressBar(
                self.loading_frame,
                width=190,
                height=8,
                corner_radius=0,
                border_width=0,
                progress_color=INK,
                fg_color=RULE,
            )
        )
        self.loading_progress.set(0)
        self.loading_progress.place(relx=0.5, rely=0.61, anchor="center")
        self.animate_loading_progress()

        self.update_time()
        self.update_noise()
        self.update_quote()
        self.update_progress()
        if self.app.song is not None:
            # Spotify is already connected, so skip the splash.
            self.loading_frame.place_forget()
            self.loading_visible = False
            self.show_song(self.app.song)

    def update_time(self) -> None:
        self.time_label.configure(text=get_time())
        self.after(REFRESH_TIME * 1000, self.update_time)

    def update_noise(self) -> None:
        self.noise_label.configure(
            text=drift_noise(self.noise_label.cget("text"), 0.05, self.noise_rng)
        )
        self.after(160, self.update_noise)

    def update_quote(self) -> None:
        self.user_label.configure(text=QUOTES[self.quote_index])
        self.quote_index = (self.quote_index + 1) % len(QUOTES)
        self.after(30_000, self.update_quote)

    def start_window_drag(self, event: tk.Event[tk.Misc]) -> None:
        self.drag_start_x = event.x_root - self.winfo_x()
        self.drag_start_y = event.y_root - self.winfo_y()

    def minimize_window(self) -> None:
        self.always_on_top = False
        self.always_on_top_var.set(False)
        self.attributes("-topmost", False)
        self.iconify()

    def close_window(self, _event: tk.Event[tk.Misc] | None = None) -> str:
        self.app.close_player()
        return "break"

    def destroy(self) -> None:
        cancel_pending_after(self)
        super().destroy()

    def restore_topmost(self, _event: tk.Event[tk.Misc] | None = None) -> None:
        if self.always_on_top:
            self.attributes("-topmost", True)

    def drag_window(self, event: tk.Event[tk.Misc]) -> None:
        x: int = event.x_root - self.drag_start_x
        y: int = event.y_root - self.drag_start_y
        self.geometry(f"+{x}+{y}")

    def show_context_menu(self, event: tk.Event[tk.Misc]) -> None:
        if self.context_menu is not None:
            self.context_menu.destroy()

        menu = customtkinter.CTkToplevel(self)
        self.context_menu = menu
        menu.overrideredirect(True)
        menu.attributes("-topmost", True)
        menu.configure(fg_color=BACKGROUND)
        # CTk scales the size but not the position, which is in screen pixels.
        menu.geometry(f"320x372+{event.x_root}+{event.y_root}")
        menu.bind("<Escape>", lambda _: self.close_context_menu())
        menu.focus_force()

        frame = customtkinter.CTkFrame(
            menu,
            fg_color=BACKGROUND,
            border_color=INK,
            border_width=outline_width(self),
            corner_radius=0,
        )
        frame.pack(fill="both", expand=True)

        title = customtkinter.CTkLabel(
            frame,
            text=f"  {APP_NAME}",
            anchor="w",
            text_color=INK,
            font=customtkinter.CTkFont(family=MONO_FONT, size=11, weight="bold"),
        )
        title.pack(fill="x", padx=8, pady=(10, 5))

        self.add_menu_button(frame, "Open hub", self.app.open_hub)
        self.add_menu_button(frame, "Open Spotify", self.open_spotify)
        self.add_menu_button(
            frame,
            f"{'✓' if self.always_on_top_var.get() else ' '}  Always on top",
            self.toggle_menu_always_on_top,
        )

        size_frame = customtkinter.CTkFrame(frame, fg_color="transparent")
        size_frame.pack(fill="x", padx=8, pady=2)
        size_label = customtkinter.CTkLabel(
            size_frame,
            text="  Size",
            anchor="w",
            text_color=INK_SOFT,
            font=customtkinter.CTkFont(family=MONO_FONT, size=11),
        )
        size_label.pack(side="left", fill="x", expand=True)
        for size_name in APP_SIZES:
            button = customtkinter.CTkButton(
                size_frame,
                text=size_name,
                width=29,
                height=24,
                corner_radius=0,
                fg_color=INK if size_name == self.size_var.get()
                else "transparent",
                hover_color=INK_SOFT if size_name == self.size_var.get()
                else HOVER,
                text_color=BACKGROUND if size_name == self.size_var.get()
                else MUTED,
                font=customtkinter.CTkFont(family=MONO_FONT, size=10, weight="bold"),
                command=lambda name=size_name: self.set_menu_size(name),
            )
            button.pack(side="left", padx=1)

        self.add_menu_button(frame, "Refresh song", self.refresh_song)
        update_button = self.add_menu_button(
            frame,
            "Check for updates",
            self.check_for_updates,
        )
        if not self.update_check_enabled:
            update_button.configure(state="disabled")
        self.add_menu_button(frame, f"About {APP_NAME}", self.show_about)
        self.add_menu_button(frame, "Close player", self.close_window)
        self.add_menu_button(
            frame,
            f"Quit {APP_NAME}",
            self.app.quit_app,
            text_color=ACCENT_DARK,
        )

    def add_menu_button(
        self,
        parent: customtkinter.CTkFrame,
        text: str,
        command: Any,
        text_color: str = INK_SOFT,
    ) -> customtkinter.CTkButton:
        button = customtkinter.CTkButton(
            parent,
            text=text,
            command=lambda: self.invoke_menu_command(command),
            anchor="w",
            height=32,
            corner_radius=0,
            fg_color="transparent",
            hover_color=HOVER,
            text_color=text_color,
            font=customtkinter.CTkFont(family=MONO_FONT, size=11),
        )
        button.pack(fill="x", padx=8, pady=2)
        return button

    def invoke_menu_command(self, command: Any) -> None:
        self.close_context_menu()
        command()

    def close_context_menu(self) -> None:
        if self.context_menu is not None:
            self.context_menu.destroy()
            self.context_menu = None

    def toggle_menu_always_on_top(self) -> None:
        self.always_on_top_var.set(not self.always_on_top_var.get())
        self.toggle_always_on_top()
        self.close_context_menu()

    def set_menu_size(self, size_name: str) -> None:
        self.set_app_size(size_name)
        self.close_context_menu()

    def open_spotify(self) -> None:
        if not webbrowser.open("spotify:"):
            webbrowser.open("https://open.spotify.com/")

    def show_about(self) -> None:
        dialog = customtkinter.CTkToplevel(self)
        dialog.title(f"About {APP_NAME}")
        dialog.geometry("330x285")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        dialog.configure(fg_color=BACKGROUND)

        card = customtkinter.CTkFrame(
            dialog,
            fg_color=BACKGROUND,
            border_color=INK,
            border_width=outline_width(self),
            corner_radius=0,
        )
        card.pack(fill="both", expand=True, padx=8, pady=8)
        customtkinter.CTkLabel(
            card,
            text=APP_NAME,
            text_color=INK,
            font=customtkinter.CTkFont(family=MONO_FONT, size=22, weight="bold"),
        ).pack(pady=(22, 2))
        customtkinter.CTkLabel(
            card,
            text=f"version {APP_VERSION}",
            text_color=MUTED,
            font=customtkinter.CTkFont(family=MONO_FONT, size=11),
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
            font=customtkinter.CTkFont(family=MONO_FONT, size=10),
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
            font=customtkinter.CTkFont(family=MONO_FONT, size=11),
            command=dialog.destroy,
        ).pack(pady=(0, 14))

    def toggle_always_on_top(self) -> None:
        self.always_on_top = self.always_on_top_var.get()
        self.attributes("-topmost", self.always_on_top)

    def set_app_size(self, size_name: str) -> None:
        size = APP_SIZES.get(size_name)
        if size is None:
            raise ValueError(f"Unknown app size: {size_name}")

        geometry, scaling = size
        self.size_var.set(size_name)
        self.current_size_name = size_name
        self.app.size_name = size_name
        customtkinter.set_widget_scaling(scaling)
        customtkinter.set_window_scaling(scaling)
        self.geometry(geometry)
        width = int(geometry.split("x", maxsplit=1)[0])
        self.song_label.configure(wraplength=max(180, width - 40))
        for button in (self.previous_button, self.next_button):
            button.configure(border_width=outline_width(self))
        # Scaling is app-wide, so the hub resizes with the player.
        if self.app.hub is not None:
            self.app.hub.refresh_outlines()
        self.user_label.configure(wraplength=max(180, width - 40))
        self.controls_frame.pack_configure(
            pady=(16, 20)
            if size_name == self.smallest_size_name
            else (10, 14)
        )
        self.show_controls()

    def handle_pointer_motion(self, event: tk.Event[tk.Misc]) -> None:
        return

    def hide_controls(self) -> None:
        if not self.controls_visible:
            return
        self.controls_frame.pack_forget()
        self.controls_visible = False

    def show_controls(self) -> None:
        if self.controls_visible:
            return
        self.controls_frame.pack(
            fill="x",
            padx=16,
            pady=(
                (16, 20)
                if self.current_size_name == self.smallest_size_name
                else (10, 14)
            ),
        )
        self.controls_visible = True

    def refresh_song(self) -> None:
        self.app.refresh_song()

    def change_volume(self, value: float) -> None:
        if self.volume_update_active:
            return

        volume_percent = round(value)
        if volume_percent == self.volume_percent:
            return

        self.volume_percent = volume_percent
        self.volume_update_active = True
        future: Future[None] = self.app.worker.submit(set_volume, volume_percent)
        future.add_done_callback(self.volume_update_finished)

    def volume_update_finished(self, future: Future[None]) -> None:
        self.after(0, self.apply_volume_update, future)

    def apply_volume_update(self, future: Future[None]) -> None:
        self.volume_update_active = False
        if not self.winfo_exists():
            return
        try:
            future.result()
        except Exception:
            self.volume_label.configure(text="vol unavailable")
            self.after(2000, lambda: self.volume_label.configure(text="vol"))

    @staticmethod
    def parse_version(version: str) -> tuple[int, ...]:
        return updater.parse_version(version)

    @staticmethod
    def find_update() -> tuple[str, str] | None:
        return updater.find_update()

    @staticmethod
    def download_update(download_url: str) -> Path:
        return updater.download_update(download_url)

    def check_for_updates(self) -> None:
        if os.name != "nt" or not getattr(sys, "frozen", False):
            messagebox.showinfo(
                "Updates",
                "Automatic updates are available for the Windows executable "
                "distributed through GitHub Releases.",
                parent=self,
            )
            return

        self.update_check_enabled = False
        self.close_context_menu()
        self.app.worker.submit(self.find_update).add_done_callback(
            self.update_check_finished
        )

    def update_check_finished(
        self,
        future: Future[tuple[str, str] | None],
    ) -> None:
        self.after(0, self.apply_update_check, future)

    def apply_update_check(
        self,
        future: Future[tuple[str, str] | None],
    ) -> None:
        self.update_check_enabled = True
        if not self.winfo_exists():
            return
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
                f"{APP_NAME} {APP_VERSION} is up to date.",
                parent=self,
            )
            return

        tag_name, download_url = update
        if messagebox.askyesno(
            "Update available",
            f"{APP_NAME} {tag_name} is available. Download and install it now?",
            parent=self,
        ):
            self.app.worker.submit(
                self.download_update,
                download_url,
            ).add_done_callback(self.update_download_finished)

    def update_download_finished(self, future: Future[Path]) -> None:
        self.after(0, self.apply_downloaded_update, future)

    def apply_downloaded_update(self, future: Future[Path]) -> None:
        try:
            download_path = future.result()
            updater.install_update(download_path)
        except Exception as error:
            messagebox.showerror(
                "Update failed",
                f"Could not install the update:\n{error}",
                parent=self,
            )
            return
        self.app.quit_app()

    def show_song_error(self) -> None:
        self.artist_label.configure(text="Spotify unavailable :<")
        self.loading_title.configure(text="Connecting to Spotify...")
        self.loading_status.configure(text="Please open Spotify and try again ♡")

    def show_song(self, song: dict[str, Any]) -> None:
        username = str(song.get("username") or "Spotify user")
        self.user_label.configure(text=f"hii {username} !")
        self.finish_loading(username)
        self.song_label.configure(text=str(song["title"]))
        self.artist_label.configure(text=song["artist"])
        album: str = song["album"]
        device: str = song["device"]
        metadata: str = " • ".join(value for value in (album, device) if value)
        self.track_meta_label.configure(text=metadata)
        self.play_pause_button.configure(
            text="||" if song["is_playing"] else ">"
        )
        duration_ms: int = song["duration_ms"]
        self.progress_ms = song["progress_ms"]
        self.duration_ms = duration_ms
        self.is_playing = song["is_playing"]
        self.progress_updated_at = time.monotonic()
        volume_percent = song["volume_percent"]
        if isinstance(volume_percent, (int, float)):
            self.volume_percent = int(volume_percent)
            self.volume_slider.set(self.volume_percent)

    def finish_loading(self, username: str) -> None:
        if not self.loading_visible:
            return

        self.loading_title.configure(text=f"hii {username} !")
        self.loading_status.configure(text="Spotify connected ♡")
        elapsed = time.monotonic() - self.loading_started_at
        remaining_ms = max(0, (MIN_LOADING_TIME - elapsed) * 1000)
        self.after(
            round(remaining_ms) + 550,
            self.animate_loading_fade,
        )

    def animate_loading_progress(self) -> None:
        if not self.loading_visible:
            self.loading_progress_id = None
            return

        elapsed = time.monotonic() - self.loading_started_at
        self.loading_progress_value = min(
            1.0,
            elapsed / MIN_LOADING_TIME,
        )
        self.loading_progress.set(self.loading_progress_value)
        if self.loading_progress_value >= 1.0:
            self.loading_progress_id = None
            return

        self.loading_progress_id = self.after(
            16,
            self.animate_loading_progress,
        )

    def animate_loading_fade(self, step: int = 0) -> None:
        if not self.loading_visible:
            return

        fade_steps = 24
        fade_amount = min(step + 1, fade_steps) / fade_steps
        background = BACKGROUND
        title_color = self.blend_color(INK, background, fade_amount)
        status_color = self.blend_color(MUTED, background, fade_amount)
        bar_color = self.blend_color(INK, background, fade_amount)
        bar_background = self.blend_color(RULE, background, fade_amount)
        self.loading_title.configure(text_color=title_color)
        self.loading_status.configure(text_color=status_color)
        self.loading_progress.configure(
            progress_color=bar_color,
            fg_color=bar_background,
        )
        if step >= fade_steps:
            self.loading_frame.place_forget()
            self.loading_visible = False
            self.loading_animation_id = None
            return

        self.loading_animation_id = self.after(
            16,
            self.animate_loading_fade,
            step + 1,
        )

    @staticmethod
    def blend_color(
        start: str,
        end: str,
        amount: float,
    ) -> str:
        start_rgb = tuple(
            int(start[index:index + 2], 16)
            for index in (1, 3, 5)
        )
        end_rgb = tuple(
            int(end[index:index + 2], 16)
            for index in (1, 3, 5)
        )
        channels = (
            round(
                start_channel
                + (end_channel - start_channel) * amount
            )
            for start_channel, end_channel in zip(start_rgb, end_rgb)
        )
        return "#" + "".join(f"{channel:02x}" for channel in channels)

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
        self.after(100, self.update_progress)

    def change_playback_position(self, value: float) -> None:
        if not self.duration_ms:
            return

        self.progress_ms = round(value * self.duration_ms)
        self.progress_updated_at = time.monotonic()
        if self.seek_after_id is not None:
            self.after_cancel(self.seek_after_id)
        self.seek_after_id = self.after(300, self.seek_to_current_position)

    def seek_to_current_position(self) -> None:
        self.seek_after_id = None
        position_ms = max(0, min(self.progress_ms, self.duration_ms))
        self.app.worker.submit(seek_playback, position_ms)

    @staticmethod
    def format_time(milliseconds: int) -> str:
        total_seconds: int = milliseconds // 1000
        minutes: int
        seconds: int
        minutes, seconds = divmod(total_seconds, 60)
        return f"{minutes}:{seconds:02d}"

    def set_album_art(self, image: Image.Image) -> None:
        self.album_art = customtkinter.CTkImage(
            light_image=image,
            dark_image=image,
            size=(ALBUM_ART_SIZE, ALBUM_ART_SIZE),
        )
        self.album_art_label.configure(image=self.album_art, text="")

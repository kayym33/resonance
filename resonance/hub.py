from __future__ import annotations

import random
import tkinter as tk
from typing import TYPE_CHECKING, Any

import customtkinter
from PIL import Image

from .ascii_art import drift_noise, noise_line
from .backend import REFRESH_TIME, get_time
from .constants import (
    APP_NAME,
    BACKGROUND,
    FAINT,
    HOVER,
    INK,
    INK_SOFT,
    MONO_FONT,
    MUTED,
)
from .calendar_page import CalendarPage
from .launcher_panel import LauncherPanel
from .todo_panel import TodoPanel
from .weather_panel import WeatherPanel
from .windows import (
    add_rule,
    cancel_pending_after,
    outline_width,
    prepare_window,
)

if TYPE_CHECKING:
    from .app import ResonanceApp

HUB_GEOMETRY = "760x640"
WEATHER_COLUMN_WIDTH = 330
PAGES: tuple[str, ...] = ("home", "calendar")
HUB_ART_SIZE = 144


def mono(size: int, weight: str = "normal") -> customtkinter.CTkFont:
    return customtkinter.CTkFont(family=MONO_FONT, size=size, weight=weight)


class HubWindow(customtkinter.CTkToplevel):
    """Main window: launcher and panels, with a pop-out for the player."""

    def __init__(self, app: ResonanceApp) -> None:
        super().__init__(app)
        self.app: ResonanceApp = app
        self.title(APP_NAME)
        self.geometry(HUB_GEOMETRY)
        self.resizable(False, False)
        self.configure(fg_color=BACKGROUND)
        self.protocol("WM_DELETE_WINDOW", self.close_window)
        self.bind("<Control-q>", self.app.quit_app)
        self.bind("<Control-w>", self.close_window)
        prepare_window(self)
        self.noise_rng: random.Random = random.Random()
        self.album_art: customtkinter.CTkImage | None = None

        self.noise_label: customtkinter.CTkLabel = customtkinter.CTkLabel(
            self,
            text=noise_line(120, self.noise_rng),
            font=mono(8),
            text_color=FAINT,
            height=12,
        )
        self.noise_label.pack(fill="x", pady=(6, 0))

        header = customtkinter.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(4, 0))
        customtkinter.CTkLabel(
            header,
            text=APP_NAME,
            font=mono(15, "bold"),
            text_color=INK,
        ).pack(side="left")
        self.page_tabs: dict[str, customtkinter.CTkButton] = {}
        for page_name in PAGES:
            tab = customtkinter.CTkButton(
                header,
                text=page_name,
                width=len(page_name) * 9 + 24,
                height=24,
                corner_radius=0,
                fg_color="transparent",
                hover_color=HOVER,
                font=mono(12, "bold"),
                command=lambda chosen=page_name: self.show_page(chosen),
            )
            tab.pack(side="left", padx=(16 if page_name == PAGES[0] else 2, 0))
            self.page_tabs[page_name] = tab
        self.time_label: customtkinter.CTkLabel = customtkinter.CTkLabel(
            header,
            text="",
            font=mono(15),
            text_color=INK_SOFT,
        )
        self.time_label.pack(side="right")

        add_rule(self, INK, padx=24, pady=(6, 10))

        self.launcher: LauncherPanel = LauncherPanel(self, self.app)
        self.launcher.pack(fill="x", padx=24, pady=(0, 10))

        # Pages swap in below the launcher, which stays on every page.
        self.home_page = customtkinter.CTkFrame(self, fg_color="transparent")
        self.calendar_page: CalendarPage | None = None
        self.page_name: str = PAGES[0]

        customtkinter.CTkLabel(
            self.home_page,
            text="NOW PLAYING",
            font=mono(10, "bold"),
            text_color=MUTED,
            anchor="w",
            height=16,
        ).pack(fill="x", padx=24)

        now_playing = customtkinter.CTkFrame(
            self.home_page,
            fg_color="transparent",
        )
        now_playing.pack(fill="x", padx=24, pady=(8, 0))

        self.album_art_label: customtkinter.CTkLabel = customtkinter.CTkLabel(
            now_playing,
            text="",
            width=HUB_ART_SIZE,
            height=HUB_ART_SIZE,
        )
        self.album_art_label.pack(side="left")

        info = customtkinter.CTkFrame(now_playing, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True, padx=(20, 0))

        self.song_label: customtkinter.CTkLabel = customtkinter.CTkLabel(
            info,
            text="Checking Spotify...",
            font=mono(16, "bold"),
            text_color=INK,
            anchor="w",
            justify="left",
            wraplength=500,
        )
        self.song_label.pack(fill="x", pady=(8, 0))
        self.artist_label: customtkinter.CTkLabel = customtkinter.CTkLabel(
            info,
            text="",
            font=mono(12),
            text_color=INK_SOFT,
            anchor="w",
        )
        self.artist_label.pack(fill="x", pady=(2, 0))
        self.meta_label: customtkinter.CTkLabel = customtkinter.CTkLabel(
            info,
            text="",
            font=mono(10),
            text_color=MUTED,
            anchor="w",
        )
        self.meta_label.pack(fill="x")

        controls = customtkinter.CTkFrame(info, fg_color="transparent")
        controls.pack(anchor="w", pady=(14, 0))
        self.outlined_buttons: list[customtkinter.CTkButton] = [
            self.add_outlined_button(controls, "|<", 48, self.app.previous_song),
        ]
        self.play_pause_button: customtkinter.CTkButton = (
            customtkinter.CTkButton(
                controls,
                text=">",
                width=56,
                height=34,
                corner_radius=0,
                border_width=0,
                fg_color=INK,
                hover_color=INK_SOFT,
                text_color=BACKGROUND,
                font=mono(14, "bold"),
                command=self.app.toggle_playback,
            )
        )
        self.play_pause_button.pack(side="left", padx=(0, 6))
        self.outlined_buttons += [
            self.add_outlined_button(controls, ">|", 48, self.app.next_song),
            self.add_outlined_button(
                controls,
                "pop out ->",
                110,
                self.app.open_player,
                padx=(16, 0),
            ),
        ]

        columns = customtkinter.CTkFrame(self.home_page, fg_color="transparent")
        columns.pack(fill="x", padx=24, pady=(28, 0))
        weather_column = customtkinter.CTkFrame(
            columns,
            width=WEATHER_COLUMN_WIDTH,
            fg_color="transparent",
        )
        weather_column.pack(side="left", fill="y")
        weather_column.pack_propagate(False)
        self.weather_panel: WeatherPanel = WeatherPanel(
            weather_column,
            self.app,
        )
        self.weather_panel.pack(fill="x")
        self.todo_panel: TodoPanel = TodoPanel(columns)
        self.todo_panel.pack(side="left", fill="both", expand=True, padx=(24, 0))

        self.show_page(PAGES[0])
        self.set_album_art(self.app.album_art_image)
        if self.app.song is not None:
            self.show_song(self.app.song)
        self.update_time()
        self.update_noise()
        # The suggestion dropdown floats above the panels packed after it.
        self.launcher.dropdown.lift()
        self.after(150, self.focus_launcher)

    def show_page(self, name: str) -> None:
        if name == "calendar" and self.calendar_page is None:
            # Built on first visit to keep the hub quick to open.
            self.calendar_page = CalendarPage(self)
        pages = {"home": self.home_page, "calendar": self.calendar_page}
        for page_name, page in pages.items():
            if page is not None and page_name != name:
                page.pack_forget()
        if name == "home":
            self.home_page.pack(fill="both", expand=True)
        else:
            pages[name].pack(fill="both", expand=True, padx=24, pady=(0, 16))
        self.page_name = name
        for page_name, tab in self.page_tabs.items():
            selected = page_name == name
            tab.configure(
                text=f"[{page_name}]" if selected else page_name,
                text_color=INK if selected else MUTED,
            )
        # Keep the launcher's dropdown above newly packed pages.
        self.launcher.dropdown.lift()

    def focus_launcher(self) -> None:
        self.focus_force()
        self.launcher.focus_prompt()

    def add_outlined_button(
        self,
        parent: customtkinter.CTkFrame,
        text: str,
        width: int,
        command: Any,
        padx: tuple[int, int] = (0, 6),
    ) -> customtkinter.CTkButton:
        button = customtkinter.CTkButton(
            parent,
            text=text,
            width=width,
            height=34,
            corner_radius=0,
            border_width=outline_width(self),
            border_color=INK,
            fg_color="transparent",
            hover_color=HOVER,
            text_color=INK,
            font=mono(12, "bold"),
            command=command,
        )
        button.pack(side="left", padx=padx)
        return button

    def refresh_outlines(self) -> None:
        for button in self.outlined_buttons:
            button.configure(border_width=outline_width(self))
        self.weather_panel.refresh_outlines()
        self.todo_panel.refresh_outlines()
        self.launcher.refresh_outlines()

    def update_time(self) -> None:
        self.time_label.configure(text=get_time())
        self.after(REFRESH_TIME * 1000, self.update_time)

    def update_noise(self) -> None:
        self.noise_label.configure(
            text=drift_noise(self.noise_label.cget("text"), 0.05, self.noise_rng)
        )
        self.after(160, self.update_noise)

    def show_song(self, song: dict[str, Any]) -> None:
        self.song_label.configure(text=str(song["title"]))
        self.artist_label.configure(text=song["artist"])
        self.meta_label.configure(
            text=" • ".join(
                value for value in (song["album"], song["device"]) if value
            )
        )
        self.play_pause_button.configure(
            text="||" if song["is_playing"] else ">"
        )

    def show_song_error(self) -> None:
        self.song_label.configure(text="Spotify unavailable :<")
        self.artist_label.configure(text="Please open Spotify and try again")
        self.meta_label.configure(text="")

    def set_album_art(self, image: Image.Image) -> None:
        self.album_art = customtkinter.CTkImage(
            light_image=image,
            dark_image=image,
            size=(HUB_ART_SIZE, HUB_ART_SIZE),
        )
        self.album_art_label.configure(image=self.album_art)

    def close_window(self, _event: tk.Event[tk.Misc] | None = None) -> str:
        self.app.close_hub()
        return "break"

    def destroy(self) -> None:
        cancel_pending_after(self)
        super().destroy()

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import customtkinter

from .ascii_art import ThemedImage
from .constants import MARGIN, MONO_FONT, MUTED, SECTION_GAP
from .now_playing_panel import NowPlayingPanel
from .starfield import Starfield
from .today_panel import TodayPanel
from .todo_panel import TodoPanel
from .weather_panel import WeatherPanel

if TYPE_CHECKING:
    from .app import ResonanceApp

WEATHER_COLUMN_WIDTH = 340
HOME_ART_SIZE = 144


def mono(size: int, weight: str = "normal") -> customtkinter.CTkFont:
    return customtkinter.CTkFont(family=MONO_FONT, size=size, weight=weight)


class HomePage(customtkinter.CTkFrame):
    """The hub's main page: today, now playing, weather and to-dos."""

    def __init__(self, parent: customtkinter.CTkFrame, app: ResonanceApp) -> None:
        super().__init__(parent, fg_color="transparent")
        self.today_panel: TodayPanel = TodayPanel(self, app)
        self.today_panel.pack(fill="x", padx=MARGIN, pady=(0, 24))

        customtkinter.CTkLabel(
            self,
            text="NOW PLAYING",
            font=mono(10, "bold"),
            text_color=MUTED,
            anchor="w",
            height=16,
        ).pack(fill="x", padx=MARGIN)
        self.now_playing: NowPlayingPanel = NowPlayingPanel(
            self,
            app,
            HOME_ART_SIZE,
        )
        self.now_playing.pack(fill="x", padx=MARGIN, pady=(12, 0))

        columns = customtkinter.CTkFrame(self, fg_color="transparent")
        columns.pack(fill="x", padx=MARGIN, pady=(SECTION_GAP, 0))
        weather_column = customtkinter.CTkFrame(
            columns,
            width=WEATHER_COLUMN_WIDTH,
            fg_color="transparent",
        )
        weather_column.pack(side="left", fill="y")
        weather_column.pack_propagate(False)
        self.weather_panel: WeatherPanel = WeatherPanel(weather_column, app)
        self.weather_panel.pack(fill="x")
        Starfield(weather_column, 0.03, 0.12).pack(
            fill="both",
            expand=True,
            pady=(24, 0),
        )
        self.todo_panel: TodoPanel = TodoPanel(columns)
        self.todo_panel.pack(side="left", fill="both", expand=True, padx=(40, 0))
        Starfield(self, 0.12, 0.22).pack(fill="both", expand=True)

    def on_show(self) -> None:
        # The weather app may have changed the location meanwhile.
        self.weather_panel.reload()

    def data_changed(self, kinds: set[str]) -> None:
        if kinds & {"task", "event"}:
            self.today_panel.refresh()
        if "task" in kinds:
            self.todo_panel.reload()
        if "setting" in kinds:
            self.weather_panel.reload()

    def show_song(self, song: dict[str, Any]) -> None:
        self.now_playing.show_song(song)

    def show_song_error(self) -> None:
        self.now_playing.show_song_error()

    def set_album_art(self, images: ThemedImage) -> None:
        self.now_playing.set_album_art(images)

    def refresh_outlines(self) -> None:
        self.now_playing.refresh_outlines()
        self.weather_panel.refresh_outlines()
        self.todo_panel.refresh_outlines()

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import customtkinter

from ..ascii_art import ThemedImage
from ..constants import MARGIN, MONO_FONT, MUTED
from ..now_playing_panel import NowPlayingPanel
from ..starfield import Starfield
from . import HubApp

if TYPE_CHECKING:
    from ..app import ResonanceApp

MUSIC_ART_SIZE = 260


class MusicPage(customtkinter.CTkFrame):
    """Now playing, with bigger album art than the home page."""

    def __init__(self, parent: customtkinter.CTkFrame, app: ResonanceApp) -> None:
        super().__init__(parent, fg_color="transparent")
        customtkinter.CTkLabel(
            self,
            text="NOW PLAYING",
            font=customtkinter.CTkFont(family=MONO_FONT, size=10, weight="bold"),
            text_color=MUTED,
            anchor="w",
            height=16,
        ).pack(fill="x", padx=MARGIN)
        self.now_playing: NowPlayingPanel = NowPlayingPanel(
            self,
            app,
            MUSIC_ART_SIZE,
            wraplength=380,
            bar_cells=32,
            show_volume=True,
        )
        self.now_playing.pack(fill="x", padx=MARGIN, pady=(12, 0))
        Starfield(self, 0.05, 0.22).pack(fill="both", expand=True)

    def show_song(self, song: dict[str, Any]) -> None:
        self.now_playing.show_song(song)

    def show_song_error(self) -> None:
        self.now_playing.show_song_error()

    def set_album_art(self, images: ThemedImage) -> None:
        self.now_playing.set_album_art(images)

    def refresh_outlines(self) -> None:
        self.now_playing.refresh_outlines()


APP = HubApp(
    name="music",
    build=MusicPage,
    order=10,
    description="now playing on Spotify",
)

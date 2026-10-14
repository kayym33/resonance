from __future__ import annotations

import time
from typing import Any

import customtkinter

from .ascii_art import ThemedImage
from .constants import BACKGROUND, INK, INK_SOFT, MONO_FONT, MUTED
from .windows import cancel_pending_after

IDLE_ART_SIZE = 96
# The big clock shows seconds, unlike the hub's own clock.
CLOCK_FORMAT = "%H:%M:%S"


def mono(size: int, weight: str = "normal") -> customtkinter.CTkFont:
    return customtkinter.CTkFont(family=MONO_FONT, size=size, weight=weight)


class IdleView(customtkinter.CTkFrame):
    """What full screen shows once nobody's used the hub for a while: a
    very big clock, and the current song if one is playing."""

    def __init__(self, parent: customtkinter.CTkToplevel) -> None:
        super().__init__(parent, fg_color=BACKGROUND, corner_radius=0)
        self.time_label = customtkinter.CTkLabel(
            self,
            text="",
            font=mono(220, "bold"),
            text_color=INK,
        )
        self.time_label.pack(padx=40, pady=(10, 0))

        self.music = customtkinter.CTkFrame(self, fg_color="transparent")
        self.art: customtkinter.CTkImage | None = None
        self.art_label = customtkinter.CTkLabel(
            self.music,
            text="",
            width=IDLE_ART_SIZE,
            height=IDLE_ART_SIZE,
        )
        self.art_label.pack(side="left")
        text = customtkinter.CTkFrame(self.music, fg_color="transparent")
        text.pack(side="left", padx=(20, 0))
        self.tick_id: str | None = None
        self.title_label = customtkinter.CTkLabel(
            text,
            text="",
            font=mono(22, "bold"),
            text_color=INK,
            anchor="w",
        )
        self.title_label.pack(fill="x")
        self.artist_label = customtkinter.CTkLabel(
            text,
            text="",
            font=mono(15),
            text_color=INK_SOFT,
            anchor="w",
        )
        self.artist_label.pack(fill="x")
        customtkinter.CTkLabel(
            text,
            text="now playing",
            font=mono(11),
            text_color=MUTED,
            anchor="w",
        ).pack(fill="x", pady=(4, 0))
        self.show_time()

    def show_time(self) -> None:
        self.time_label.configure(text=time.strftime(CLOCK_FORMAT))

    def start(self) -> None:
        """Tick once a second while shown, on the second, so the seconds
        never skip or repeat."""
        self.stop()
        self.show_time()
        until_next_second = 1000 - int(time.time() * 1000) % 1000
        self.tick_id = self.after(until_next_second + 5, self.start)

    def stop(self) -> None:
        if self.tick_id is not None:
            self.after_cancel(self.tick_id)
            self.tick_id = None

    def show_song(self, song: dict[str, Any] | None) -> None:
        if not song or not song.get("is_playing"):
            self.music.pack_forget()
            return
        self.title_label.configure(text=str(song["title"]))
        self.artist_label.configure(text=str(song["artist"]))
        if self.music.winfo_manager() != "pack":
            self.music.pack(pady=(0, 30))

    def set_album_art(self, images: ThemedImage) -> None:
        self.art = customtkinter.CTkImage(
            light_image=images[0],
            dark_image=images[1],
            size=(IDLE_ART_SIZE, IDLE_ART_SIZE),
        )
        self.art_label.configure(image=self.art)

    def destroy(self) -> None:
        cancel_pending_after(self)
        super().destroy()

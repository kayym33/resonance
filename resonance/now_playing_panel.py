from __future__ import annotations

import time
import tkinter as tk
from typing import TYPE_CHECKING, Any, Callable

import customtkinter

from .ascii_art import ThemedImage
from .constants import BACKGROUND, HOVER, INK, INK_SOFT, MONO_FONT, MUTED
from .windows import cancel_pending_after, outline_width

if TYPE_CHECKING:
    from .app import ResonanceApp


PROGRESS_TICK_MS = 500


def mono(size: int, weight: str = "normal") -> customtkinter.CTkFont:
    return customtkinter.CTkFont(family=MONO_FONT, size=size, weight=weight)


def format_ms(milliseconds: int) -> str:
    minutes, seconds = divmod(max(0, milliseconds) // 1000, 60)
    return f"{minutes}:{seconds:02d}"


class TextMeter(customtkinter.CTkLabel):
    """A bar drawn in text, like the battery's "[###··]", followed by a
    caption. Clicking a cell calls ``on_click`` with that fraction."""

    def __init__(
        self,
        parent: customtkinter.CTkFrame,
        cells: int,
        on_click: Callable[[float], None],
        prefix: str = "",
    ) -> None:
        super().__init__(
            parent,
            text="",
            font=mono(11),
            text_color=INK_SOFT,
            anchor="w",
            corner_radius=0,
            height=16,
            cursor="hand2",
        )
        self.cells: int = cells
        self.prefix: str = prefix
        self.on_click: Callable[[float], None] = on_click
        self.bind("<Button-1>", self.clicked)

    def set(self, fraction: float, caption: str) -> None:
        filled = round(max(0.0, min(1.0, fraction)) * self.cells)
        bar = "#" * filled + "·" * (self.cells - filled)
        text = f"{self.prefix}[{bar}]  {caption}"
        # Labels redraw on every configure, so only when the text changes.
        if text != self.cget("text"):
            self.configure(text=text)

    def clicked(self, event: tk.Event[tk.Misc]) -> None:
        text = self.cget("text")
        if not text:
            return
        # Monospace: every character is the same width, and the label is
        # packed at its natural width, so its text starts at its left edge.
        char_width = self.winfo_width() / len(text)
        cell = (event.x_root - self.winfo_rootx()) / char_width - len(self.prefix) - 1
        if -1 <= cell <= self.cells:
            self.on_click(max(0.0, min(1.0, (cell + 0.5) / self.cells)))


class NowPlayingPanel(customtkinter.CTkFrame):
    """Album art, the current song and playback controls."""

    def __init__(
        self,
        parent: customtkinter.CTkFrame,
        app: ResonanceApp,
        art_size: int,
        wraplength: int = 500,
        bar_cells: int = 24,
        show_volume: bool = False,
    ) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app: ResonanceApp = app
        self.art_size: int = art_size
        self.album_art: customtkinter.CTkImage | None = None
        # The progress counts on between Spotify polls.
        self.progress_ms: int = 0
        self.duration_ms: int = 0
        self.is_playing: bool = False
        self.progress_at: float = time.monotonic()

        self.album_art_label: customtkinter.CTkLabel = customtkinter.CTkLabel(
            self,
            text="",
            width=art_size,
            height=art_size,
        )
        self.album_art_label.pack(side="left")

        info = customtkinter.CTkFrame(self, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True, padx=(28, 0))

        self.song_label: customtkinter.CTkLabel = customtkinter.CTkLabel(
            info,
            text="Checking Spotify...",
            font=mono(16, "bold"),
            text_color=INK,
            anchor="w",
            justify="left",
            wraplength=wraplength,
        )
        self.song_label.pack(fill="x", pady=(6, 0))
        self.artist_label: customtkinter.CTkLabel = customtkinter.CTkLabel(
            info,
            text="",
            font=mono(12),
            text_color=INK_SOFT,
            anchor="w",
        )
        self.artist_label.pack(fill="x", pady=(4, 0))
        self.meta_label: customtkinter.CTkLabel = customtkinter.CTkLabel(
            info,
            text="",
            font=mono(10),
            text_color=MUTED,
            anchor="w",
        )
        self.meta_label.pack(fill="x", pady=(2, 0))

        self.progress: TextMeter = TextMeter(info, bar_cells, self.seek)
        self.progress.pack(anchor="w", pady=(12, 0))
        self.volume: TextMeter | None = None
        if show_volume:
            self.volume = TextMeter(info, 10, self.set_volume, prefix="vol ")
            self.volume.pack(anchor="w", pady=(4, 0))

        controls = customtkinter.CTkFrame(info, fg_color="transparent")
        controls.pack(anchor="w", pady=(16, 0))
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
        self.play_pause_button.pack(side="left", padx=(0, 8))
        self.outlined_buttons += [
            self.add_outlined_button(controls, ">|", 48, self.app.next_song),
            self.add_outlined_button(
                controls,
                "pop out ->",
                110,
                self.app.open_player,
                padx=(20, 0),
            ),
        ]

        self.set_album_art(self.app.album_art_image)
        if self.app.song is not None:
            self.show_song(self.app.song)
        self.update_progress()

    def add_outlined_button(
        self,
        parent: customtkinter.CTkFrame,
        text: str,
        width: int,
        command: Any,
        padx: tuple[int, int] = (0, 8),
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
        self.progress_ms = song["progress_ms"] or 0
        self.duration_ms = song["duration_ms"] or 0
        self.is_playing = bool(song["is_playing"])
        self.progress_at = time.monotonic()
        self.update_progress(reschedule=False)
        volume = song["volume_percent"]
        if self.volume is None:
            return
        if isinstance(volume, (int, float)):
            self.volume.set(volume / 100, f"{round(volume)}%")
        else:
            # Nothing playing, or a device without volume control.
            self.volume.configure(text="")

    def show_song_error(self) -> None:
        self.song_label.configure(text="Spotify unavailable :<")
        self.artist_label.configure(text="Please open Spotify and try again")
        self.meta_label.configure(text="")
        self.duration_ms = 0
        self.update_progress(reschedule=False)
        if self.volume is not None:
            self.volume.configure(text="")

    def position_ms(self) -> int:
        position = self.progress_ms
        if self.is_playing:
            position += int((time.monotonic() - self.progress_at) * 1000)
        return min(position, self.duration_ms)

    def update_progress(self, reschedule: bool = True) -> None:
        if self.duration_ms:
            position = self.position_ms()
            self.progress.set(
                position / self.duration_ms,
                f"{format_ms(position)} / {format_ms(self.duration_ms)}",
            )
        elif self.progress.cget("text"):
            self.progress.configure(text="")
        if reschedule:
            self.after(PROGRESS_TICK_MS, self.update_progress)

    def seek(self, fraction: float) -> None:
        if not self.duration_ms:
            return
        self.progress_ms = round(fraction * self.duration_ms)
        self.progress_at = time.monotonic()
        self.update_progress(reschedule=False)
        self.app.seek(self.progress_ms)

    def set_volume(self, fraction: float) -> None:
        percent = round(fraction * 100)
        if self.volume is not None:
            self.volume.set(fraction, f"{percent}%")
        self.app.change_volume(percent)

    def destroy(self) -> None:
        cancel_pending_after(self)
        super().destroy()

    def set_album_art(self, images: ThemedImage) -> None:
        self.album_art = customtkinter.CTkImage(
            light_image=images[0],
            dark_image=images[1],
            size=(self.art_size, self.art_size),
        )
        self.album_art_label.configure(image=self.album_art)

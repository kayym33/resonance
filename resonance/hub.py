from __future__ import annotations

import os
import time
import tkinter as tk
from typing import TYPE_CHECKING, Any

import customtkinter

from .ascii_art import ThemedImage
from .backend import REFRESH_TIME, get_time
from .constants import (
    ACCENT_DARK,
    APP_NAME,
    BACKGROUND,
    HOVER,
    INK,
    INK_SOFT,
    MONO_FONT,
    MUTED,
)
from .battery import describe as describe_battery
from .battery import read_battery
from .calendar_page import CalendarPage
from .idle_view import IdleView
from .launcher_panel import LauncherPanel
from .menu import SIZE_ROW, MenuItem
from .noise_band import NoiseBand
from .starfield import Starfield
from .today_panel import TodayPanel
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

HUB_SIZE = (820, 770)
HUB_GEOMETRY = f"{HUB_SIZE[0]}x{HUB_SIZE[1]}"
# Full screen swaps the hub for a big clock after this long untouched.
IDLE_AFTER_S = 45
ACTIVITY_CHECK_MS = 500
BATTERY_CHECK_MS = 30_000
# Star density around the hub in full screen.
BACKDROP_DENSITY = 0.2
# Wide enough to run off both edges of the window.
NOISE_COLUMNS = 170
WEATHER_COLUMN_WIDTH = 340
# Side margin and the gap between sections.
MARGIN = 36
SECTION_GAP = 32
PAGES: tuple[str, ...] = ("home", "calendar")
HUB_ART_SIZE = 144
AVATAR_ICON_SIZE = 28


def mono(size: int, weight: str = "normal") -> customtkinter.CTkFont:
    return customtkinter.CTkFont(family=MONO_FONT, size=size, weight=weight)


class HubWindow(customtkinter.CTkToplevel):
    """Main window: launcher and panels, with a pop-out for the player."""

    def __init__(self, app: ResonanceApp) -> None:
        super().__init__(app)
        self.app: ResonanceApp = app
        self.title(APP_NAME)
        self.geometry(HUB_GEOMETRY)
        # Resizable (so the title bar has a maximize button, which goes full
        # screen) but never smaller than the hub's layout.
        self.minsize(*HUB_SIZE)
        self.configure(fg_color=BACKGROUND)
        self.protocol("WM_DELETE_WINDOW", self.close_window)
        self.bind("<Control-q>", self.app.quit_app)
        self.bind("<Control-w>", self.close_window)
        self.bind("<Button-3>", self.show_context_menu)
        # A left click anywhere else in the window closes an open menu.
        self.bind("<Button-1>", lambda _event: self.app.close_context_menu())
        self.bind("<F11>", lambda _event: self.toggle_fullscreen())
        self.bind("<Escape>", self.exit_fullscreen)
        self.bind("<Configure>", self.on_configure)
        # Activity that keeps full screen from going idle. Pointer movement
        # is polled in check_activity instead of bound.
        for sequence in ("<KeyRelease>", "<ButtonRelease>", "<MouseWheel>"):
            self.bind(sequence, self.note_activity)
        prepare_window(self)
        self.album_art: customtkinter.CTkImage | None = None
        self.fullscreen: bool = False

        # Full screen centres the hub in a field of stars. The backdrop is
        # created first so the content stacks above it.
        self.backdrop = Starfield(self, BACKDROP_DENSITY, BACKDROP_DENSITY)
        self.content = customtkinter.CTkFrame(
            self,
            width=HUB_SIZE[0],
            height=HUB_SIZE[1],
            corner_radius=0,
            fg_color="transparent",
        )
        self.content.pack_propagate(False)
        self.content.pack(fill="both", expand=True)
        self.idle_view = IdleView(self)
        # "normal" (packed), "expanded" (centred in stars) or "idle".
        self.layout: str = "normal"
        self.idle: bool = False
        self.last_activity: float = time.monotonic()
        self.last_pointer: tuple[int, int] | None = None

        # Stars that thin out towards the content. The bottom field is
        # packed now so it keeps its place below the pages; the home page
        # fills its own spare space with more, growing denser downwards.
        NoiseBand(self.content, NOISE_COLUMNS, (0.55, 0.32, 0.16)).pack(
            fill="x",
            pady=(8, 0),
        )
        Starfield(self.content, 0.22, 0.45, height=56).pack(
            side="bottom",
            fill="x",
        )

        header = customtkinter.CTkFrame(self.content, fg_color="transparent")
        header.pack(fill="x", padx=MARGIN, pady=(8, 0))
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
        # Only packed on computers with a battery (see update_battery).
        self.battery_label: customtkinter.CTkLabel = customtkinter.CTkLabel(
            header,
            text="",
            font=mono(12),
        )
        self.account_button: customtkinter.CTkButton = customtkinter.CTkButton(
            header,
            text="",
            width=0,
            height=24,
            corner_radius=0,
            fg_color="transparent",
            hover_color=HOVER,
            font=mono(12),
            command=lambda: self.app.open_account(self),
        )
        self.account_button.pack(side="right", padx=(0, 18))
        self.avatar_icon: customtkinter.CTkImage | None = None
        self.avatar_label: customtkinter.CTkLabel = customtkinter.CTkLabel(
            header,
            text="",
            width=AVATAR_ICON_SIZE,
            height=AVATAR_ICON_SIZE,
            cursor="hand2",
        )
        self.avatar_label.bind("<Button-1>", lambda _event: self.app.open_account(self))
        self.show_account()

        add_rule(self.content, INK, padx=MARGIN, pady=(10, 14))

        self.launcher: LauncherPanel = LauncherPanel(self.content, self.app)
        self.launcher.pack(fill="x", padx=MARGIN, pady=(0, 8))

        # Pages swap in below the launcher, which stays on every page.
        self.home_page = customtkinter.CTkFrame(
            self.content,
            fg_color="transparent",
        )
        self.calendar_page: CalendarPage | None = None
        self.page_name: str = PAGES[0]

        self.today_panel: TodayPanel = TodayPanel(self.home_page, self.app)
        self.today_panel.pack(fill="x", padx=MARGIN, pady=(0, 24))

        customtkinter.CTkLabel(
            self.home_page,
            text="NOW PLAYING",
            font=mono(10, "bold"),
            text_color=MUTED,
            anchor="w",
            height=16,
        ).pack(fill="x", padx=MARGIN)

        now_playing = customtkinter.CTkFrame(
            self.home_page,
            fg_color="transparent",
        )
        now_playing.pack(fill="x", padx=MARGIN, pady=(12, 0))

        self.album_art_label: customtkinter.CTkLabel = customtkinter.CTkLabel(
            now_playing,
            text="",
            width=HUB_ART_SIZE,
            height=HUB_ART_SIZE,
        )
        self.album_art_label.pack(side="left")

        info = customtkinter.CTkFrame(now_playing, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True, padx=(28, 0))

        self.song_label: customtkinter.CTkLabel = customtkinter.CTkLabel(
            info,
            text="Checking Spotify...",
            font=mono(16, "bold"),
            text_color=INK,
            anchor="w",
            justify="left",
            wraplength=500,
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

        controls = customtkinter.CTkFrame(info, fg_color="transparent")
        controls.pack(anchor="w", pady=(18, 0))
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

        columns = customtkinter.CTkFrame(self.home_page, fg_color="transparent")
        columns.pack(fill="x", padx=MARGIN, pady=(SECTION_GAP, 0))
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
        Starfield(weather_column, 0.03, 0.12).pack(
            fill="both",
            expand=True,
            pady=(24, 0),
        )
        self.todo_panel: TodoPanel = TodoPanel(columns)
        self.todo_panel.pack(side="left", fill="both", expand=True, padx=(40, 0))
        Starfield(self.home_page, 0.12, 0.22).pack(fill="both", expand=True)

        self.show_page(PAGES[0])
        self.set_album_art(self.app.album_art_image)
        if self.app.song is not None:
            self.show_song(self.app.song)
        self.update_time()
        self.update_battery()
        # The suggestion dropdown floats above the panels packed after it.
        self.launcher.dropdown.lift()
        self.after(150, self.focus_launcher)
        self.after(ACTIVITY_CHECK_MS, self.check_activity)

    def show_page(self, name: str) -> None:
        if name == "calendar" and self.calendar_page is None:
            # Built on first visit to keep the hub quick to open.
            self.calendar_page = CalendarPage(self.content)
        pages = {"home": self.home_page, "calendar": self.calendar_page}
        for page_name, page in pages.items():
            if page is not None and page_name != name:
                page.pack_forget()
        if name == "home":
            self.home_page.pack(fill="both", expand=True)
        else:
            pages[name].pack(fill="both", expand=True, padx=MARGIN, pady=(0, 24))
        self.page_name = name
        for page_name, tab in self.page_tabs.items():
            selected = page_name == name
            tab.configure(
                text=f"[{page_name}]" if selected else page_name,
                text_color=INK if selected else MUTED,
            )
        # Keep the launcher's dropdown above newly packed pages.
        self.launcher.dropdown.lift()

    def show_account(self) -> None:
        text, problem = self.app.account_label()
        self.account_button.configure(
            text=text,
            text_color=ACCENT_DARK if problem else MUTED,
        )
        if self.app.sync.session is None:
            self.avatar_label.pack_forget()
            return
        _large, icon = self.app.avatar_images()
        self.avatar_icon = customtkinter.CTkImage(
            light_image=icon[0],
            dark_image=icon[1],
            size=(AVATAR_ICON_SIZE, AVATAR_ICON_SIZE),
        )
        self.avatar_label.configure(image=self.avatar_icon)
        if self.avatar_label.winfo_manager() != "pack":
            # Packed after the name button, so it sits just left of it.
            self.avatar_label.pack(side="right", padx=(0, 2))

    def toggle_fullscreen(self) -> None:
        self.set_fullscreen(not self.fullscreen)

    def exit_fullscreen(self, _event: tk.Event[tk.Misc] | None = None) -> str | None:
        if not self.fullscreen:
            return None
        if self.idle:
            # The first Esc just wakes the hub back up.
            self.note_activity()
        else:
            self.set_fullscreen(False)
        return "break"

    def set_fullscreen(self, fullscreen: bool) -> None:
        if fullscreen == self.fullscreen:
            return
        self.fullscreen = fullscreen
        if fullscreen:
            self.note_activity()
            self.update_idletasks()
            self.attributes("-fullscreen", True)
        else:
            self.set_idle(False)
            self.attributes("-fullscreen", False)
            self.update_idletasks()
            self.geometry(HUB_GEOMETRY)
        self.apply_layout()

    def on_configure(self, event: tk.Event[tk.Misc]) -> None:
        if event.widget is not self:
            return  # Children's resizes bubble up here too.
        if not self.fullscreen and self.is_maximized():
            # The title bar's maximize button means full screen here.
            self.after_idle(self.maximize_to_fullscreen)
            return
        self.apply_layout()

    def is_maximized(self) -> bool:
        if os.name == "nt":
            return self.state() == "zoomed"
        try:
            return bool(self.attributes("-zoomed"))
        except tk.TclError:
            return False

    def maximize_to_fullscreen(self) -> None:
        if os.name == "nt":
            self.state("normal")
        else:
            self.attributes("-zoomed", False)
        self.set_fullscreen(True)

    def apply_layout(self) -> None:
        """Pack the hub normally, or centre it (or the idle clock) in a
        field of stars when the window is full screen or bigger than it."""
        expanded = (
            self.fullscreen
            or self.winfo_width() > self.content.winfo_reqwidth() + 4
            or self.winfo_height() > self.content.winfo_reqheight() + 4
        )
        layout = "idle" if self.idle else "expanded" if expanded else "normal"
        if layout == self.layout:
            return
        self.layout = layout
        for widget in (self.content, self.idle_view, self.backdrop):
            widget.pack_forget()
            widget.place_forget()
        if layout == "normal":
            self.content.pack(fill="both", expand=True)
        else:
            self.backdrop.place(relx=0, rely=0, relwidth=1, relheight=1)
            shown = self.idle_view if layout == "idle" else self.content
            shown.place(relx=0.5, rely=0.5, anchor="center")
        self.launcher.dropdown.lift()

    # Idle clock (full screen only)

    def note_activity(self, _event: tk.Event[tk.Misc] | None = None) -> None:
        self.last_activity = time.monotonic()
        if self.idle:
            self.set_idle(False)

    def check_activity(self) -> None:
        if self.fullscreen:
            pointer = self.winfo_pointerxy()
            if pointer != self.last_pointer:
                self.last_pointer = pointer
                self.note_activity()
            elif (
                not self.idle
                and time.monotonic() - self.last_activity >= IDLE_AFTER_S
            ):
                self.set_idle(True)
        self.after(ACTIVITY_CHECK_MS, self.check_activity)

    def set_idle(self, idle: bool) -> None:
        if idle == self.idle:
            return
        self.idle = idle
        if idle:
            self.app.close_context_menu()
            self.idle_view.start()
            self.idle_view.show_song(self.app.song)
        else:
            self.idle_view.stop()
        self.configure(cursor="none" if idle else "")
        self.apply_layout()

    def show_context_menu(self, event: tk.Event[tk.Misc]) -> None:
        self.app.show_context_menu(
            self,
            event,
            [
                MenuItem("Pop out player", self.app.open_player),
                MenuItem("Open Spotify", self.app.open_spotify),
                MenuItem(
                    f"Theme: {self.app.theme_choice()}",
                    self.app.cycle_theme,
                ),
                MenuItem("Account", lambda: self.app.open_account(self)),
                SIZE_ROW,
                MenuItem("Refresh song", self.app.refresh_song),
                MenuItem(
                    "Check for updates",
                    lambda: self.app.check_for_updates(self),
                    enabled=self.app.update_check_enabled,
                ),
                MenuItem(f"About {APP_NAME}", lambda: self.app.show_about(self)),
                MenuItem(
                    "Exit full screen" if self.fullscreen else "Full screen",
                    self.toggle_fullscreen,
                ),
                MenuItem("Close hub", self.close_window),
                MenuItem(f"Quit {APP_NAME}", self.app.quit_app, ACCENT_DARK),
            ],
        )

    def focus_launcher(self) -> None:
        self.focus_force()
        self.launcher.focus_prompt()

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
        self.weather_panel.refresh_outlines()
        self.todo_panel.refresh_outlines()
        self.launcher.refresh_outlines()

    def update_battery(self) -> None:
        battery = read_battery()
        if battery is None:
            self.battery_label.pack_forget()
        else:
            self.battery_label.configure(
                text=describe_battery(battery),
                text_color=ACCENT_DARK if battery.low else MUTED,
            )
            if self.battery_label.winfo_manager() != "pack":
                # Packed after the clock, so it sits just left of it.
                self.battery_label.pack(
                    side="right",
                    padx=(0, 18),
                    after=self.time_label,
                )
        self.after(BATTERY_CHECK_MS, self.update_battery)

    def update_time(self) -> None:
        self.time_label.configure(text=get_time())
        self.after(REFRESH_TIME * 1000, self.update_time)

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
        self.idle_view.show_song(song)

    def show_song_error(self) -> None:
        self.song_label.configure(text="Spotify unavailable :<")
        self.artist_label.configure(text="Please open Spotify and try again")
        self.meta_label.configure(text="")

    def set_album_art(self, images: ThemedImage) -> None:
        self.album_art = customtkinter.CTkImage(
            light_image=images[0],
            dark_image=images[1],
            size=(HUB_ART_SIZE, HUB_ART_SIZE),
        )
        self.album_art_label.configure(image=self.album_art)
        self.idle_view.set_album_art(images)

    def close_window(self, _event: tk.Event[tk.Misc] | None = None) -> str:
        self.app.close_hub()
        return "break"

    def destroy(self) -> None:
        cancel_pending_after(self)
        super().destroy()

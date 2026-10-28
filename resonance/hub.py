from __future__ import annotations

import os
import time
import tkinter as tk
from typing import TYPE_CHECKING, Any

import customtkinter

from .ascii_art import ThemedImage
from .backend import REFRESH_TIME, get_time
from .apps import HubApp, discover
from .constants import (
    ACCENT_DARK,
    APP_NAME,
    BACKGROUND,
    HOVER,
    INK,
    INK_SOFT,
    MARGIN,
    MONO_FONT,
    MUTED,
)
from .battery import describe as describe_battery
from .battery import read_battery
from .home_page import HomePage
from .idle_view import IdleView
from .launcher_panel import LauncherPanel
from .menu import SIZE_ROW, MenuItem
from .noise_band import NoiseBand
from .starfield import Starfield
from .windows import (
    add_rule,
    cancel_pending_after,
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
AVATAR_ICON_SIZE = 28
HOME = "home"
# Room for the trail between the name and the header's right-hand side,
# counting " / " between crumbs. Measured to clear the account name.
TRAIL_CHARS = 44
CRUMB_CHARS = 24
# The trail reuses this many buttons rather than making new ones on
# every navigation, since each new widget costs tens of milliseconds.
MAX_CRUMBS = 6
APP_MENU_WIDTH = 440


def shorten(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def trail_length(crumbs: list[str]) -> int:
    return sum(len(crumb) + 3 for crumb in crumbs)


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
        NoiseBand(self.content, NOISE_COLUMNS, (0.5, 0.22)).pack(
            fill="x",
            pady=(4, 0),
        )
        Starfield(self.content, 0.22, 0.45, height=56).pack(
            side="bottom",
            fill="x",
        )

        header = customtkinter.CTkFrame(self.content, fg_color="transparent")
        header.pack(fill="x", padx=MARGIN, pady=(4, 0))
        self.menu_button: customtkinter.CTkButton = customtkinter.CTkButton(
            header,
            text="≡",
            width=24,
            height=24,
            corner_radius=0,
            fg_color="transparent",
            hover_color=HOVER,
            text_color=INK,
            font=mono(16, "bold"),
            command=self.open_app_menu,
        )
        self.menu_button.pack(side="left", padx=(0, 10))
        title = customtkinter.CTkButton(
            header,
            text=APP_NAME,
            width=0,
            height=24,
            corner_radius=0,
            fg_color="transparent",
            hover_color=HOVER,
            text_color=INK,
            font=mono(15, "bold"),
            command=lambda: self.show_page(HOME),
        )
        title.pack(side="left")
        # "/ cookbook / recipes" next to the name while an app is open.
        # An empty CTkFrame asks for 200x200 by default, which on the home
        # page (no crumbs) made the whole header row that tall.
        self.trail_frame: customtkinter.CTkFrame = customtkinter.CTkFrame(
            header,
            width=1,
            height=1,
            fg_color="transparent",
        )
        self.trail_frame.pack(side="left", padx=(2, 0))
        self.trails: dict[str, list[str]] = {}
        self.crumbs: list[customtkinter.CTkButton] = [
            customtkinter.CTkButton(
                self.trail_frame,
                text="",
                width=0,
                height=24,
                corner_radius=0,
                fg_color="transparent",
                hover_color=HOVER,
                text_color=MUTED,
                font=mono(15),
            )
            for _ in range(MAX_CRUMBS)
        ]
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

        add_rule(self.content, INK, padx=MARGIN, pady=(6, 8))

        self.launcher: LauncherPanel = LauncherPanel(self.content, self.app)
        self.launcher.pack(fill="x", padx=MARGIN, pady=(0, 4))

        # Pages swap in below the launcher, which stays on every page. Home
        # is built now; each app's page is built the first time it opens.
        self.hub_apps: dict[str, HubApp] = {
            hub_app.name: hub_app for hub_app in discover() if hub_app.name != HOME
        }
        self.home: HomePage = HomePage(self.content, self.app)
        self.pages: dict[str, customtkinter.CTkFrame] = {HOME: self.home}
        self.page_name: str = ""
        self.show_page(HOME)

        self.update_time()
        self.update_battery()
        # The suggestion dropdown floats above the panels packed after it.
        self.launcher.dropdown.lift()
        self.after(150, self.focus_launcher)
        self.after(ACTIVITY_CHECK_MS, self.check_activity)

    # Pages

    def show_page(self, name: str) -> None:
        if name not in self.pages:
            self.pages[name] = self.hub_apps[name].build(self.content, self.app)
        if name != self.page_name:
            for page_name, page in self.pages.items():
                if page_name != name:
                    page.pack_forget()
            self.pages[name].pack(fill="both", expand=True)
            self.page_name = name
            self.render_trail()
            # Keep the launcher's dropdown above newly packed pages.
            self.launcher.dropdown.lift()
        self.call_pages("on_show", only=name)

    def call_pages(self, method: str, *args: Any, only: str | None = None) -> None:
        """Call an optional page hook (see apps/__init__.py) on every built
        page, or on just one."""
        for page_name, page in list(self.pages.items()):
            if only is not None and page_name != only:
                continue
            hook = getattr(page, method, None)
            if hook is not None:
                hook(*args)

    def data_changed(self, kinds: set[str]) -> None:
        self.call_pages("data_changed", kinds)

    def set_trail(self, page: customtkinter.CTkFrame, parts: list[str]) -> None:
        """Show where an app is inside itself: ``["recipes", "carbonara"]``
        reads "t1ld3 / cookbook / recipes / carbonara"."""
        name = next(
            (page_name for page_name, built in self.pages.items() if built is page),
            None,
        )
        if name is None:
            return
        self.trails[name] = list(parts)
        if name == self.page_name:
            self.render_trail()

    def render_trail(self) -> None:
        crumbs = (
            []
            if self.page_name == HOME
            else [self.page_name, *self.trails.get(self.page_name, [])]
        )
        crumbs = [shorten(crumb, CRUMB_CHARS) for crumb in crumbs][:MAX_CRUMBS]
        # Fold the early middle crumbs into "…" (still clickable), keeping
        # the one just before the end for context, then shorten that one.
        for depth in range(1, len(crumbs) - 2):
            if trail_length(crumbs) <= TRAIL_CHARS:
                break
            crumbs[depth] = "…"
        if len(crumbs) > 2 and trail_length(crumbs) > TRAIL_CHARS:
            spare = TRAIL_CHARS - trail_length(crumbs) + len(crumbs[-2])
            crumbs[-2] = shorten(crumbs[-2], max(8, spare))
        go_to_trail = getattr(self.pages[self.page_name], "go_to_trail", None)
        for depth, (crumb, button) in enumerate(zip(crumbs, self.crumbs)):
            # The last crumb is where you are, so it isn't a link.
            link = depth < len(crumbs) - 1 and go_to_trail is not None
            button.configure(
                text=f"/ {crumb}",
                text_color=MUTED if link else INK_SOFT,
                hover=link,
                command=(lambda chosen=depth: go_to_trail(chosen)) if link else None,
            )
        # Showing and hiding buttons costs far more than relabelling them,
        # so only the ones past the old or new length change.
        for depth, button in enumerate(self.crumbs):
            shown = button.winfo_manager() == "pack"
            if depth < len(crumbs) and not shown:
                button.pack(side="left", padx=(2, 0))
            elif depth >= len(crumbs) and shown:
                button.pack_forget()

    def open_app_menu(self) -> None:
        names = [HOME, *self.hub_apps]
        descriptions = {name: hub_app.description for name, hub_app in self.hub_apps.items()}
        descriptions[HOME] = "today at a glance"
        items = [
            MenuItem(
                name,
                lambda chosen=name: self.show_page(chosen),
                detail=descriptions[name] or " ",
                # 1 to 9 open the first nine pages while the menu is open.
                key=str(number) if number <= 9 else "",
                current=name == self.page_name,
            )
            for number, name in enumerate(names, start=1)
        ]
        button = self.menu_button
        self.app.show_menu_at(
            self,
            button.winfo_rootx(),
            button.winfo_rooty() + button.winfo_height(),
            items,
            width=APP_MENU_WIDTH,
        )

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

    def refresh_outlines(self) -> None:
        self.call_pages("refresh_outlines")
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
        self.call_pages("show_song", song)
        self.idle_view.show_song(song)

    def show_song_error(self) -> None:
        self.call_pages("show_song_error")

    def set_album_art(self, images: ThemedImage) -> None:
        self.call_pages("set_album_art", images)
        self.idle_view.set_album_art(images)

    def close_window(self, _event: tk.Event[tk.Misc] | None = None) -> str:
        self.app.close_hub()
        return "break"

    def destroy(self) -> None:
        cancel_pending_after(self)
        super().destroy()

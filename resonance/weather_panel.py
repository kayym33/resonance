from __future__ import annotations

from concurrent.futures import Future
from typing import TYPE_CHECKING, Any, Callable

import customtkinter

from .constants import (
    ACCENT_DARK,
    BACKGROUND,
    HOVER,
    INK,
    INK_SOFT,
    MONO_FONT,
    MUTED,
)
from .settings import load_settings, save_setting
from .weather import (
    WEATHER_REFRESH_TIME,
    Location,
    get_weather,
    locate_by_ip,
    search_city,
)
from .windows import cancel_pending_after, outline_width

if TYPE_CHECKING:
    from .app import ResonanceApp

ERROR_RETRY_TIME: int = 2 * 60


def mono(size: int, weight: str = "normal") -> customtkinter.CTkFont:
    return customtkinter.CTkFont(family=MONO_FONT, size=size, weight=weight)


class WeatherPanel(customtkinter.CTkFrame):
    """Hub panel that asks where the user is, then shows the weather there.

    Settings: ``share_location`` is True (look up by IP each launch),
    False (use the saved ``weather_location``), or missing (ask first).
    """

    def __init__(
        self,
        parent: customtkinter.CTkFrame | customtkinter.CTkToplevel,
        app: ResonanceApp,
    ) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app: ResonanceApp = app
        self.location: Location | None = None
        self.request_id: int = 0
        self.refresh_id: str | None = None
        self.city_entry: customtkinter.CTkEntry | None = None
        self.showing_weather: bool = False

        header = customtkinter.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x")
        customtkinter.CTkLabel(
            header,
            text="WEATHER",
            font=mono(10, "bold"),
            text_color=MUTED,
            anchor="w",
            height=16,
        ).pack(side="left")
        self.change_button: customtkinter.CTkButton = customtkinter.CTkButton(
            header,
            text="change",
            width=60,
            height=16,
            corner_radius=0,
            fg_color="transparent",
            hover_color=HOVER,
            text_color=MUTED,
            font=mono(10),
            command=self.change_location,
        )

        self.body: customtkinter.CTkFrame = customtkinter.CTkFrame(
            self,
            fg_color="transparent",
        )
        self.body.pack(fill="x", pady=(12, 0))

        settings = load_settings()
        share_location = settings.get("share_location")
        self.location = Location.from_dict(settings.get("weather_location"))
        if share_location is True:
            self.locate()
        elif self.location is not None:
            self.fetch_weather()
        elif share_location is False:
            self.show_city_entry()
        else:
            self.show_location_prompt()

    # Screens

    def clear_body(self) -> None:
        self.change_button.pack_forget()
        self.city_entry = None
        self.showing_weather = False
        for child in self.body.winfo_children():
            child.destroy()

    def show_status(self, text: str) -> None:
        self.clear_body()
        customtkinter.CTkLabel(
            self.body,
            text=text,
            font=mono(11),
            text_color=MUTED,
            anchor="w",
        ).pack(fill="x")

    def show_location_prompt(self) -> None:
        self.clear_body()
        customtkinter.CTkLabel(
            self.body,
            text="Share your location for local weather?",
            font=mono(12),
            text_color=INK,
            anchor="w",
        ).pack(fill="x")
        customtkinter.CTkLabel(
            self.body,
            text="Uses your IP address to find your nearest city.",
            font=mono(10),
            text_color=MUTED,
            anchor="w",
        ).pack(fill="x")
        buttons = customtkinter.CTkFrame(self.body, fg_color="transparent")
        buttons.pack(anchor="w", pady=(10, 0))
        self.add_button(buttons, "share", self.choose_share, solid=True)
        self.add_button(buttons, "enter a city", self.choose_city)

    def show_city_entry(self, error: str = "") -> None:
        self.clear_body()
        row = customtkinter.CTkFrame(self.body, fg_color="transparent")
        row.pack(anchor="w")
        self.city_entry = customtkinter.CTkEntry(
            row,
            width=240,
            height=32,
            corner_radius=0,
            border_width=outline_width(self),
            border_color=INK,
            text_color=INK,
            placeholder_text="city, e.g. Glasgow",
            font=mono(12),
        )
        self.city_entry.pack(side="left", padx=(0, 6))
        self.city_entry.bind("<Return>", lambda _event: self.submit_city())
        self.city_entry.focus_set()
        self.add_button(row, "ok", self.submit_city, solid=True)
        if error:
            customtkinter.CTkLabel(
                self.body,
                text=error,
                font=mono(10),
                text_color=ACCENT_DARK,
                anchor="w",
            ).pack(fill="x", pady=(4, 0))

    def show_weather(self, weather: dict[str, Any]) -> None:
        self.clear_body()
        self.showing_weather = True
        self.change_button.pack(side="right")
        customtkinter.CTkLabel(
            self.body,
            text="\n".join(weather["icon"]),
            font=mono(10),
            text_color=INK_SOFT,
            justify="left",
            anchor="w",
        ).pack(side="left")
        details = customtkinter.CTkFrame(self.body, fg_color="transparent")
        details.pack(side="left", fill="x", expand=True, padx=(18, 0))
        customtkinter.CTkLabel(
            details,
            text=f"{weather['temperature']}°C  {weather['description']}",
            font=mono(18, "bold"),
            text_color=INK,
            anchor="w",
        ).pack(fill="x")
        customtkinter.CTkLabel(
            details,
            text=(
                f"feels {weather['feels_like']}°  ·  "
                f"H {weather['high']}°  L {weather['low']}°"
            ),
            font=mono(11),
            text_color=MUTED,
            anchor="w",
        ).pack(fill="x")
        customtkinter.CTkLabel(
            details,
            text=weather["location"],
            font=mono(11),
            text_color=INK_SOFT,
            anchor="w",
        ).pack(fill="x", pady=(4, 0))

    def add_button(
        self,
        parent: customtkinter.CTkFrame,
        text: str,
        command: Callable[[], None],
        solid: bool = False,
    ) -> customtkinter.CTkButton:
        button = customtkinter.CTkButton(
            parent,
            text=text,
            width=max(48, len(text) * 9 + 24),
            height=32,
            corner_radius=0,
            border_width=0 if solid else outline_width(self),
            border_color=INK,
            fg_color=INK if solid else "transparent",
            hover_color=INK_SOFT if solid else HOVER,
            text_color=BACKGROUND if solid else INK,
            font=mono(11, "bold"),
            command=command,
        )
        button.pack(side="left", padx=(0, 6))
        return button

    # Choices

    def choose_share(self) -> None:
        save_setting("share_location", True)
        save_setting("weather_location", None)
        self.locate()

    def choose_city(self) -> None:
        save_setting("share_location", False)
        self.show_city_entry()

    def change_location(self) -> None:
        self.cancel_refresh()
        self.request_id += 1
        self.show_location_prompt()

    def submit_city(self) -> None:
        if self.city_entry is None:
            return
        name = self.city_entry.get().strip()
        if not name:
            return
        self.show_status(f"looking up {name}...")
        self.submit(
            lambda future: self.apply_city(future, name),
            search_city,
            name,
        )

    # Requests

    def submit(
        self,
        on_done: Callable[[Future[Any]], None],
        function: Callable[..., Any],
        *args: Any,
    ) -> None:
        # Only the newest request may update the panel.
        self.request_id += 1
        request_id = self.request_id
        future: Future[Any] = self.app.worker.submit(function, *args)
        future.add_done_callback(
            lambda completed: self.request_finished(
                completed,
                request_id,
                on_done,
            )
        )

    def request_finished(
        self,
        future: Future[Any],
        request_id: int,
        on_done: Callable[[Future[Any]], None],
    ) -> None:
        self.after(0, self.apply_request, future, request_id, on_done)

    def apply_request(
        self,
        future: Future[Any],
        request_id: int,
        on_done: Callable[[Future[Any]], None],
    ) -> None:
        if request_id != self.request_id or not self.winfo_exists():
            return
        on_done(future)

    def locate(self) -> None:
        self.show_status("finding your location...")
        self.submit(self.apply_location, locate_by_ip)

    def apply_location(self, future: Future[Location]) -> None:
        try:
            self.location = future.result()
        except Exception:
            self.show_city_entry(
                error="couldn't find your location, enter a city instead"
            )
            return
        self.fetch_weather()

    def apply_city(self, future: Future[Location | None], name: str) -> None:
        try:
            location = future.result()
        except Exception:
            self.show_city_entry(error="couldn't reach the weather service")
            return
        if location is None:
            self.show_city_entry(error=f'couldn\'t find "{name}"')
            return
        save_setting("share_location", False)
        save_setting("weather_location", location.to_dict())
        self.location = location
        self.fetch_weather()

    def fetch_weather(self) -> None:
        if self.location is None:
            return
        self.cancel_refresh()
        if not self.showing_weather:
            self.show_status(f"fetching weather for {self.location.name}...")
        self.submit(self.apply_weather, get_weather, self.location)

    def apply_weather(self, future: Future[dict[str, Any]]) -> None:
        try:
            weather = future.result()
        except Exception:
            if not self.showing_weather:
                self.show_status("weather unavailable, retrying soon")
            self.schedule_refresh(ERROR_RETRY_TIME)
            return
        self.show_weather(weather)
        self.schedule_refresh(WEATHER_REFRESH_TIME)

    def schedule_refresh(self, seconds: int) -> None:
        self.cancel_refresh()
        self.refresh_id = self.after(seconds * 1000, self.fetch_weather)

    def cancel_refresh(self) -> None:
        if self.refresh_id is not None:
            self.after_cancel(self.refresh_id)
            self.refresh_id = None

    def refresh_outlines(self) -> None:
        if self.city_entry is not None:
            self.city_entry.configure(border_width=outline_width(self))

    def destroy(self) -> None:
        cancel_pending_after(self)
        super().destroy()

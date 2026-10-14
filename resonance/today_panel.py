from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any

import customtkinter

from .constants import INK, INK_SOFT, MONO_FONT, MUTED
from .events import EVENTS, events_on, load_events
from .todo import TASKS, load_tasks
from .windows import cancel_pending_after

if TYPE_CHECKING:
    from .app import ResonanceApp

# Catches the date rolling over at midnight.
REFRESH_MS = 60_000
BUSY_MESSAGE = "good luck !!"
QUIET_MESSAGE = "nothing on today ~ enjoy !!"


def mono(size: int, weight: str = "normal") -> customtkinter.CTkFont:
    return customtkinter.CTkFont(family=MONO_FONT, size=size, weight=weight)


def weather_summary(weather: dict[str, Any] | None) -> str:
    if weather is None:
        return ""
    return (
        f"{weather['temperature']}°C {weather['description']}, "
        f"high {weather['high']}° low {weather['low']}°"
    )


class TodayPanel(customtkinter.CTkFrame):
    """A two-line briefing: today's weather, open to-dos and events."""

    def __init__(
        self,
        parent: customtkinter.CTkFrame,
        app: ResonanceApp,
    ) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app: ResonanceApp = app

        heading = customtkinter.CTkFrame(self, fg_color="transparent")
        heading.pack(fill="x")
        customtkinter.CTkLabel(
            heading,
            text="TODAY",
            font=mono(10, "bold"),
            text_color=MUTED,
            height=16,
        ).pack(side="left")
        self.date_label = customtkinter.CTkLabel(
            heading,
            text="",
            font=mono(12, "bold"),
            text_color=INK,
            height=16,
        )
        self.date_label.pack(side="left", padx=(12, 0))
        self.message_label = customtkinter.CTkLabel(
            heading,
            text="",
            font=mono(12, "bold"),
            text_color=INK,
            height=16,
        )
        self.message_label.pack(side="right")
        self.summary_label = customtkinter.CTkLabel(
            self,
            text="",
            font=mono(11),
            text_color=INK_SOFT,
            anchor="w",
            justify="left",
            wraplength=740,
        )
        self.summary_label.pack(fill="x", pady=(4, 0))

        # Local edits to to-dos and events update the briefing straight
        # away; synced ones arrive through app.data_changed.
        for collection in (TASKS, EVENTS):
            collection.listeners.append(self.refresh)
        self.refresh()
        self.after(REFRESH_MS, self.tick)

    def refresh(self) -> None:
        today = date.today()
        open_tasks = sum(1 for task in load_tasks() if not task.done)
        todays_events = events_on(load_events(), today)

        parts = [weather_summary(self.app.weather)]
        if open_tasks:
            parts.append(f"{open_tasks} to-do{'s' if open_tasks != 1 else ''} left")
        else:
            parts.append("to-dos all done")
        if todays_events:
            parts.append(", ".join(event.label() for event in todays_events))
        else:
            parts.append("nothing in the calendar")

        self.date_label.configure(text=f"{today:%A} {today.day} {today:%B}".lower())
        self.summary_label.configure(text="  ·  ".join(part for part in parts if part))
        self.message_label.configure(
            text=BUSY_MESSAGE if open_tasks or todays_events else QUIET_MESSAGE
        )

    def tick(self) -> None:
        self.refresh()
        self.after(REFRESH_MS, self.tick)

    def destroy(self) -> None:
        for collection in (TASKS, EVENTS):
            if self.refresh in collection.listeners:
                collection.listeners.remove(self.refresh)
        cancel_pending_after(self)
        super().destroy()

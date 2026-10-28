from __future__ import annotations

from typing import TYPE_CHECKING

import customtkinter

from ..calendar_page import CalendarPage
from ..constants import MARGIN
from . import HubApp

if TYPE_CHECKING:
    from ..app import ResonanceApp


class CalendarApp(customtkinter.CTkFrame):
    def __init__(self, parent: customtkinter.CTkFrame, _app: ResonanceApp) -> None:
        super().__init__(parent, fg_color="transparent")
        self.calendar: CalendarPage = CalendarPage(self)
        self.calendar.pack(fill="both", expand=True, padx=MARGIN, pady=(0, 24))

    def data_changed(self, kinds: set[str]) -> None:
        if "event" in kinds:
            self.calendar.reload()

    def refresh_outlines(self) -> None:
        self.calendar.scrollbar.rescale()


APP = HubApp(
    name="calendar",
    build=CalendarApp,
    order=40,
    description="your events: day, 3-day, week and month",
)

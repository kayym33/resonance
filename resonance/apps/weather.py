from __future__ import annotations

from typing import TYPE_CHECKING

import customtkinter

from ..constants import MARGIN
from ..starfield import Starfield
from ..weather_panel import WeatherPanel
from . import HubApp

if TYPE_CHECKING:
    from ..app import ResonanceApp


class WeatherPage(customtkinter.CTkFrame):
    def __init__(self, parent: customtkinter.CTkFrame, app: ResonanceApp) -> None:
        super().__init__(parent, fg_color="transparent")
        self.weather_panel: WeatherPanel = WeatherPanel(self, app)
        self.weather_panel.pack(fill="x", padx=MARGIN)
        Starfield(self, 0.05, 0.22).pack(fill="both", expand=True, pady=(24, 0))

    def on_show(self) -> None:
        # The home page may have changed the location meanwhile.
        self.weather_panel.reload()

    def data_changed(self, kinds: set[str]) -> None:
        if "setting" in kinds:
            self.weather_panel.reload()

    def refresh_outlines(self) -> None:
        self.weather_panel.refresh_outlines()


APP = HubApp(
    name="weather",
    build=WeatherPage,
    order=20,
    description="the forecast where you are",
)

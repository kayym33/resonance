from __future__ import annotations

from typing import TYPE_CHECKING

import customtkinter

from ..constants import MARGIN
from ..todo_panel import TodoPanel
from . import HubApp

if TYPE_CHECKING:
    from ..app import ResonanceApp

TODO_LIST_HEIGHT = 420


class TodoPage(customtkinter.CTkFrame):
    def __init__(self, parent: customtkinter.CTkFrame, _app: ResonanceApp) -> None:
        super().__init__(parent, fg_color="transparent")
        self.todo_panel: TodoPanel = TodoPanel(self, list_height=TODO_LIST_HEIGHT, detailed=True)
        self.todo_panel.pack(fill="both", expand=True, padx=MARGIN, pady=(0, 24))

    def data_changed(self, kinds: set[str]) -> None:
        if "task" in kinds:
            self.todo_panel.reload()

    def refresh_outlines(self) -> None:
        self.todo_panel.refresh_outlines()


APP = HubApp(
    name="to-do",
    build=TodoPage,
    order=30,
    description="your to-do list",
)

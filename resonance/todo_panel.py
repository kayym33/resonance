from __future__ import annotations

import customtkinter

from .constants import HOVER, INK, MONO_FONT, MUTED
from .rich_text import RichText
from .todo import TASKS, Task, add_task, delete_task, load_tasks, save_task
from .windows import outline_width

TASK_LIST_HEIGHT = 200
# Shown when the list is empty.
EMPTY_ART = (
    "  [x] [x] [x]\n"
    "   all done ~\n"
)


def mono(size: int, weight: str = "normal") -> customtkinter.CTkFont:
    return customtkinter.CTkFont(family=MONO_FONT, size=size, weight=weight)


class TodoPanel(customtkinter.CTkFrame):
    """Hub panel: add, tick off and delete tasks saved in todo.json."""

    def __init__(
        self,
        parent: customtkinter.CTkFrame,
        list_height: int = TASK_LIST_HEIGHT,
        detailed: bool = False,
    ) -> None:
        super().__init__(parent, fg_color="transparent")
        self.tasks: list[Task] = load_tasks()
        # The to-do app's copy also counts tasks and lists done ones apart.
        self.detailed: bool = detailed

        header = customtkinter.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x")
        customtkinter.CTkLabel(
            header,
            text="TO DO",
            font=mono(10, "bold"),
            text_color=MUTED,
            anchor="w",
            height=16,
        ).pack(side="left")
        self.count_label: customtkinter.CTkLabel = customtkinter.CTkLabel(
            header,
            text="",
            font=mono(10),
            text_color=MUTED,
            anchor="w",
            height=16,
        )
        if detailed:
            self.count_label.pack(side="left", padx=(12, 0))
        self.clear_button: customtkinter.CTkButton = customtkinter.CTkButton(
            header,
            text="clear done",
            width=80,
            height=16,
            corner_radius=0,
            fg_color="transparent",
            hover_color=HOVER,
            text_color=MUTED,
            font=mono(10),
            command=self.clear_done,
        )

        self.entry: customtkinter.CTkEntry = customtkinter.CTkEntry(
            self,
            height=30,
            corner_radius=0,
            border_width=outline_width(self),
            border_color=INK,
            text_color=INK,
            placeholder_text="+ add a task",
            placeholder_text_color=MUTED,
            font=mono(12),
        )
        self.entry.pack(fill="x", pady=(12, 8))
        self.entry.bind("<Return>", lambda _event: self.add_from_entry())
        self.entry.bind("<KP_Enter>", lambda _event: self.add_from_entry())

        # One text widget for the whole list, which scrolls with the wheel.
        # A CTkScrollableFrame of row widgets took seconds per edit: each
        # row added or removed redrew its scrollbar, which forced another
        # full layout pass (see rich_text.py).
        list_frame = customtkinter.CTkFrame(
            self,
            height=list_height,
            corner_radius=0,
            fg_color="transparent",
        )
        list_frame.pack(fill="x")
        list_frame.pack_propagate(False)
        self.task_list: RichText = RichText(list_frame)
        self.task_list.pack(fill="both", expand=True)
        self.render_tasks()
        # Every edit, from this panel, another copy of it or the launcher,
        # re-renders the list; synced ones arrive through reload.
        TASKS.listeners.append(self.reload)

    def add_task(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        add_task(text)

    def add_from_entry(self) -> str:
        self.add_task(self.entry.get())
        self.entry.delete(0, "end")
        return "break"

    def toggle_task(self, task: Task) -> None:
        task.done = not task.done
        save_task(task)

    def delete_task(self, task: Task) -> None:
        delete_task(task)

    def clear_done(self) -> None:
        for task in self.tasks:
            if task.done:
                delete_task(task)

    def reload(self) -> None:
        """Re-read tasks, including ones synced from other devices."""
        self.tasks = load_tasks()
        self.render_tasks()

    def render_tasks(self) -> None:
        if any(task.done for task in self.tasks):
            self.clear_button.pack(side="right")
        else:
            self.clear_button.pack_forget()

        left = sum(not task.done for task in self.tasks)
        done = len(self.tasks) - left
        count = f"{left} left · {done} done" if done else f"{left} left"
        self.count_label.configure(text=count if self.tasks else "")

        lines = self.task_list
        lines.clear()
        if not self.tasks:
            lines.write(EMPTY_ART, "faded")
            lines.end_text()
            return
        if self.detailed:
            todo = [task for task in self.tasks if not task.done]
            finished = [task for task in self.tasks if task.done]
            self.write_tasks(todo)
            if finished:
                lines.heading("done", first=not todo)
                self.write_tasks(finished)
        else:
            self.write_tasks(self.tasks)
        lines.end_text()

    def write_tasks(self, tasks: list[Task]) -> None:
        lines = self.task_list
        for task in tasks:
            # Tk takes a line's tab stops and spacing from its first
            # character, so every part of the line carries "row".
            line = ("row", "checklist")
            lines.link(
                "[x]" if task.done else "[ ]",
                lambda chosen=task: self.toggle_task(chosen),
                "faded" if task.done else "strong",
                *line,
            )
            lines.write(
                f" {task.text}",
                "faded" if task.done else "body",
                *line,
                *(("struck",) if task.done else ()),
            )
            lines.write("\t", *line)
            lines.link("x", lambda chosen=task: self.delete_task(chosen), "faded", *line)
            lines.write("\n", *line)

    def refresh_outlines(self) -> None:
        self.entry.configure(border_width=outline_width(self))
        self.task_list.rescale()

    def destroy(self) -> None:
        if self.reload in TASKS.listeners:
            TASKS.listeners.remove(self.reload)
        super().destroy()

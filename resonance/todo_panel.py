from __future__ import annotations

import customtkinter

from .constants import (
    BACKGROUND,
    HOVER,
    INK,
    INK_SOFT,
    MONO_FONT,
    MUTED,
    RULE,
)
from .todo import Task, load_tasks, save_tasks
from .windows import outline_width

TASK_LIST_HEIGHT = 200


def mono(
    size: int,
    weight: str = "normal",
    overstrike: bool = False,
) -> customtkinter.CTkFont:
    return customtkinter.CTkFont(
        family=MONO_FONT,
        size=size,
        weight=weight,
        overstrike=overstrike,
    )


class TodoPanel(customtkinter.CTkFrame):
    """Hub panel: add, tick off and delete tasks saved in todo.json."""

    def __init__(self, parent: customtkinter.CTkFrame) -> None:
        super().__init__(parent, fg_color="transparent")
        self.tasks: list[Task] = load_tasks()

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
        self.entry.pack(fill="x", pady=(8, 4))
        self.entry.bind("<Return>", lambda _event: self.add_from_entry())
        self.entry.bind("<KP_Enter>", lambda _event: self.add_from_entry())

        self.task_list: customtkinter.CTkScrollableFrame = (
            customtkinter.CTkScrollableFrame(
                self,
                height=TASK_LIST_HEIGHT,
                corner_radius=0,
                fg_color=BACKGROUND,
                scrollbar_button_color=HOVER,
                scrollbar_button_hover_color=RULE,
            )
        )
        self.task_list.pack(fill="x")
        self.render_tasks()

    def add_task(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        self.tasks.append(Task(text))
        self.save_and_render()

    def add_from_entry(self) -> str:
        self.add_task(self.entry.get())
        self.entry.delete(0, "end")
        return "break"

    def toggle_task(self, task: Task) -> None:
        task.done = not task.done
        self.save_and_render()

    def delete_task(self, task: Task) -> None:
        self.tasks.remove(task)
        self.save_and_render()

    def clear_done(self) -> None:
        self.tasks = [task for task in self.tasks if not task.done]
        self.save_and_render()

    def save_and_render(self) -> None:
        save_tasks(self.tasks)
        self.render_tasks()

    def render_tasks(self) -> None:
        for child in self.task_list.winfo_children():
            child.destroy()

        if any(task.done for task in self.tasks):
            self.clear_button.pack(side="right")
        else:
            self.clear_button.pack_forget()

        if not self.tasks:
            customtkinter.CTkLabel(
                self.task_list,
                text="nothing to do  ~",
                font=mono(11),
                text_color=MUTED,
                anchor="w",
            ).pack(fill="x", padx=4)
            return

        for task in self.tasks:
            row = customtkinter.CTkFrame(self.task_list, fg_color="transparent")
            row.pack(fill="x")
            customtkinter.CTkButton(
                row,
                text="[x]" if task.done else "[ ]",
                width=34,
                height=24,
                corner_radius=0,
                fg_color="transparent",
                hover_color=HOVER,
                text_color=MUTED if task.done else INK,
                font=mono(12, "bold"),
                command=lambda chosen=task: self.toggle_task(chosen),
            ).pack(side="left")
            customtkinter.CTkButton(
                row,
                text="x",
                width=24,
                height=24,
                corner_radius=0,
                fg_color="transparent",
                hover_color=HOVER,
                text_color=MUTED,
                font=mono(11),
                command=lambda chosen=task: self.delete_task(chosen),
            ).pack(side="right")
            customtkinter.CTkLabel(
                row,
                text=task.text,
                font=mono(12, overstrike=task.done),
                text_color=MUTED if task.done else INK_SOFT,
                anchor="w",
                justify="left",
                wraplength=280,
            ).pack(side="left", fill="x", expand=True, padx=(4, 0))

    def refresh_outlines(self) -> None:
        self.entry.configure(border_width=outline_width(self))

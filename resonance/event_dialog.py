from __future__ import annotations

from datetime import date, time
from typing import Callable

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
from .events import DEFAULT_DURATION, Event, minutes, parse_day, parse_time
from .windows import outline_width, prepare_window

DIALOG_SIZE = (380, 285)


def mono(size: int, weight: str = "normal") -> customtkinter.CTkFont:
    return customtkinter.CTkFont(family=MONO_FONT, size=size, weight=weight)


def format_time(value: time | None) -> str:
    return value.strftime("%H:%M") if value else ""


class EventDialog(customtkinter.CTkToplevel):
    """Add or edit one event. Leave the start empty for an all-day event."""

    def __init__(
        self,
        parent: customtkinter.CTkToplevel,
        day: date,
        start: time | None,
        on_save: Callable[[Event], None],
        on_delete: Callable[[Event], None],
        event: Event | None = None,
    ) -> None:
        super().__init__(parent)
        self.event: Event | None = event
        self.on_save = on_save
        self.on_delete = on_delete
        self.title("edit event" if event else "new event")
        self.resizable(False, False)
        self.configure(fg_color=BACKGROUND)
        self.transient(parent)
        prepare_window(self)
        width, height = DIALOG_SIZE
        # Centre over the parent; CTk scales the size but not the position.
        scaling = customtkinter.ScalingTracker.get_window_scaling(self)
        x = parent.winfo_rootx() + (parent.winfo_width() - width * scaling) / 2
        y = parent.winfo_rooty() + (parent.winfo_height() - height * scaling) / 3
        self.geometry(f"{width}x{height}+{round(x)}+{round(y)}")

        if event is not None:
            day, start = event.day, event.start
            end = event.end
        elif start is not None:
            end_minutes = min(24 * 60 - 1, minutes(start) + 60)
            end = time(end_minutes // 60, end_minutes % 60)
        else:
            end = None

        body = customtkinter.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=16)
        self.title_entry = self.add_field(body, "title", event.title if event else "")
        self.day_entry = self.add_field(body, "date", day.isoformat())
        times = customtkinter.CTkFrame(body, fg_color="transparent")
        times.pack(fill="x")
        self.start_entry = self.add_field(
            times,
            "start",
            format_time(start),
            side="left",
            placeholder="all day",
        )
        self.end_entry = self.add_field(
            times,
            "end",
            format_time(end),
            side="left",
            placeholder="",
        )

        self.error_label = customtkinter.CTkLabel(
            body,
            text="",
            font=mono(10),
            text_color=ACCENT_DARK,
            anchor="w",
            height=16,
        )
        self.error_label.pack(fill="x", pady=(2, 0))

        buttons = customtkinter.CTkFrame(body, fg_color="transparent")
        buttons.pack(fill="x", side="bottom")
        self.add_button(buttons, "save", self.save, solid=True)
        self.add_button(buttons, "cancel", self.destroy)
        if event is not None:
            customtkinter.CTkButton(
                buttons,
                text="delete",
                width=70,
                height=32,
                corner_radius=0,
                fg_color="transparent",
                hover_color=HOVER,
                text_color=ACCENT_DARK,
                font=mono(11, "bold"),
                command=self.delete,
            ).pack(side="left")

        self.bind("<Return>", lambda _event: self.save())
        self.bind("<KP_Enter>", lambda _event: self.save())
        self.bind("<Escape>", lambda _event: self.destroy())
        self.after(100, self.focus_title)

    def focus_title(self) -> None:
        self.grab_set()
        self.focus_force()
        self.title_entry.focus_set()

    def add_field(
        self,
        parent: customtkinter.CTkFrame,
        label: str,
        value: str,
        side: str = "top",
        placeholder: str = "",
    ) -> customtkinter.CTkEntry:
        field = customtkinter.CTkFrame(parent, fg_color="transparent")
        if side == "top":
            field.pack(fill="x", pady=(0, 10))
        else:
            field.pack(side="left", padx=(0, 12), pady=(0, 10))
        customtkinter.CTkLabel(
            field,
            text=label.upper(),
            font=mono(10, "bold"),
            text_color=MUTED,
            anchor="w",
            height=16,
        ).pack(fill="x")
        entry = customtkinter.CTkEntry(
            field,
            width=150 if side == "left" else 340,
            height=30,
            corner_radius=0,
            border_width=outline_width(self),
            border_color=INK,
            text_color=INK,
            placeholder_text=placeholder,
            placeholder_text_color=MUTED,
            font=mono(12),
        )
        entry.pack(anchor="w")
        if value:
            entry.insert(0, value)
        return entry

    def add_button(
        self,
        parent: customtkinter.CTkFrame,
        text: str,
        command: Callable[[], None],
        solid: bool = False,
    ) -> None:
        customtkinter.CTkButton(
            parent,
            text=text,
            width=80,
            height=32,
            corner_radius=0,
            border_width=0 if solid else outline_width(self),
            border_color=INK,
            fg_color=INK if solid else "transparent",
            hover_color=INK_SOFT if solid else HOVER,
            text_color=BACKGROUND if solid else INK,
            font=mono(11, "bold"),
            command=command,
        ).pack(side="right", padx=(6, 0))

    def save(self) -> str:
        title = self.title_entry.get().strip()
        try:
            if not title:
                raise ValueError("give the event a title")
            day = parse_day(self.day_entry.get())
            start = parse_time(self.start_entry.get())
            end = parse_time(self.end_entry.get()) if start else None
            if start is not None and end is None:
                end_minutes = min(
                    24 * 60 - 1,
                    minutes(start) + int(DEFAULT_DURATION.total_seconds() // 60),
                )
                end = time(end_minutes // 60, end_minutes % 60)
            if start is not None and end is not None and end <= start:
                raise ValueError("the end needs to be after the start")
        except ValueError as error:
            self.error_label.configure(text=str(error))
            return "break"

        event = self.event or Event(title, day)
        event.title, event.day, event.start, event.end = title, day, start, end
        self.on_save(event)
        self.destroy()
        return "break"

    def delete(self) -> None:
        if self.event is not None:
            self.on_delete(self.event)
        self.destroy()

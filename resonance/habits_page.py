from __future__ import annotations

from datetime import date

import customtkinter

from . import accent
from .constants import HOVER, INK, MARGIN, MONO_FONT, MUTED
from .habits import (
    DEFAULT_DONE_MESSAGE,
    DONE_MESSAGE_SETTING,
    HABITS,
    Habit,
    add_habit,
    best_streak,
    delete_habit,
    load_habits,
    streak,
    toggle_day,
    week_days,
)
from .rich_text import RichText
from .settings import SETTINGS, load_device_setting, load_settings, save_device_setting
from .sound import play_tick
from .theme import color, unwatch, watch
from .windows import cancel_pending_after, outline_width

# The week view's name column, in characters.
NAME_CHARS = 22
# The day can change while the page is open.
DATE_CHECK_MS = 60_000
DONE_CELL = "■"
OPEN_CELL = "□"
# Days still to come this week.
FUTURE_CELL = "·"
CELL_GAP = "  "
EMPTY_ART = (
    "  no habits yet ~\n"
    "  add one above, then tick it off each day\n"
)
# Device-only: whether ticking a habit plays a sound.
SOUND_SETTING = "habit_sound"


def mono(size: int, weight: str = "normal") -> customtkinter.CTkFont:
    return customtkinter.CTkFont(family=MONO_FONT, size=size, weight=weight)


def fit_name(name: str) -> str:
    if len(name) > NAME_CHARS:
        name = name[: NAME_CHARS - 1] + "…"
    return name.ljust(NAME_CHARS) + " "


def streak_text(days: int) -> str:
    return f"{days}-day streak"


class HabitsPage(customtkinter.CTkFrame):
    """Daily habits. Home lists today's: tick one off and it plays a
    short tick. "week" shows Monday to Sunday for each habit,
    where a missed day can be ticked after the fact."""

    def __init__(self, parent: customtkinter.CTkFrame, _app: object) -> None:
        super().__init__(parent, fg_color="transparent")
        self.habits: list[Habit] = load_habits()
        self.today: date = date.today()
        self.view: str = "today"  # or "week"
        # The habit whose delete button was clicked once, waiting for a
        # second click to confirm.
        self.confirming: str | None = None
        self.sound_on: bool = bool(load_device_setting(SOUND_SETTING, True))

        body = customtkinter.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=MARGIN, pady=(0, 24))

        header = customtkinter.CTkFrame(body, fg_color="transparent")
        header.pack(fill="x")
        self.title_label: customtkinter.CTkLabel = customtkinter.CTkLabel(
            header,
            text="",
            font=mono(10, "bold"),
            text_color=MUTED,
            anchor="w",
            height=16,
        )
        self.title_label.pack(side="left")
        self.count_label: customtkinter.CTkLabel = customtkinter.CTkLabel(
            header,
            text="",
            font=mono(10),
            text_color=MUTED,
            anchor="w",
            height=16,
        )
        self.count_label.pack(side="left", padx=(12, 0))
        self.sound_button: customtkinter.CTkButton = self.header_button(
            header, self.toggle_sound
        )
        self.sound_button.pack(side="right")
        self.view_button: customtkinter.CTkButton = self.header_button(
            header, self.toggle_view
        )
        self.view_button.pack(side="right", padx=(0, 8))
        self.show_sound_state()

        self.entry: customtkinter.CTkEntry = customtkinter.CTkEntry(
            body,
            height=30,
            corner_radius=0,
            border_width=outline_width(self),
            border_color=INK,
            text_color=INK,
            placeholder_text="+ add a habit",
            placeholder_text_color=MUTED,
            font=mono(12),
        )
        self.entry.pack(fill="x", pady=(12, 8))
        self.entry.bind("<Return>", lambda _event: self.add_from_entry())
        self.entry.bind("<KP_Enter>", lambda _event: self.add_from_entry())

        self.lines: RichText = RichText(body)
        self.lines.pack(fill="both", expand=True)
        self.recolor()
        watch(self.recolor)
        accent.watch(self.recolor)

        self.render()
        HABITS.listeners.append(self.reload)
        SETTINGS.listeners.append(self.render)
        self.after(DATE_CHECK_MS, self.check_date)

    def header_button(self, parent: customtkinter.CTkFrame, command: object) -> customtkinter.CTkButton:
        return customtkinter.CTkButton(
            parent,
            text="",
            width=90,
            height=16,
            corner_radius=0,
            fg_color="transparent",
            hover_color=HOVER,
            text_color=MUTED,
            font=mono(10),
            command=command,
        )

    # Hooks (see apps/__init__.py)

    def on_show(self) -> None:
        self.confirming = None
        self.reload()

    def data_changed(self, kinds: set[str]) -> None:
        if "habit" in kinds:
            self.reload()
        elif "setting" in kinds:
            self.render()

    def go_to_trail(self, depth: int) -> None:
        if depth == 0:
            self.show_view("today")

    def refresh_outlines(self) -> None:
        self.entry.configure(border_width=outline_width(self))
        self.lines.rescale()
        self.recolor()

    # Actions

    def add_from_entry(self) -> str:
        add_habit(self.entry.get())
        self.entry.delete(0, "end")
        return "break"

    def tick(self, habit: Habit, day: date) -> None:
        self.confirming = None
        if toggle_day(habit, day) and self.sound_on:
            play_tick()

    def ask_delete(self, habit: Habit) -> None:
        if self.confirming == habit.id:
            self.confirming = None
            delete_habit(habit)
        else:
            self.confirming = habit.id
            self.render()

    def toggle_view(self) -> None:
        self.show_view("week" if self.view == "today" else "today")

    def show_view(self, view: str) -> None:
        self.view = view
        self.confirming = None
        self.winfo_toplevel().set_trail(self, ["week"] if view == "week" else [])
        self.render()

    def toggle_sound(self) -> None:
        self.sound_on = not self.sound_on
        save_device_setting(SOUND_SETTING, self.sound_on)
        self.show_sound_state()
        if self.sound_on:
            play_tick()

    def show_sound_state(self) -> None:
        self.sound_button.configure(text=f"sound: {'on' if self.sound_on else 'off'}")

    def check_date(self) -> None:
        if date.today() != self.today:
            self.reload()
        self.after(DATE_CHECK_MS, self.check_date)

    # Drawing

    def recolor(self) -> None:
        self.lines.tag_configure("accent", foreground=color(accent.mark()))
        # Above the styles, which share the cells' text.
        self.lines.tag_raise("accent")

    def reload(self) -> None:
        self.habits = load_habits()
        self.render()

    def render(self) -> None:
        self.today = date.today()
        week = self.view == "week"
        self.title_label.configure(text="THIS WEEK" if week else "TODAY")
        self.view_button.configure(text="‹ today" if week else "week ›")
        done_today = sum(self.today in habit.done for habit in self.habits)
        if not self.habits:
            count = ""
        elif done_today == len(self.habits):
            message = load_settings().get(DONE_MESSAGE_SETTING)
            count = message if isinstance(message, str) and message else DEFAULT_DONE_MESSAGE
        else:
            count = f"{done_today} of {len(self.habits)} done"
        self.count_label.configure(text=count)

        lines = self.lines
        lines.clear()
        if not self.habits:
            lines.write(EMPTY_ART, "faded")
        elif week:
            self.write_week()
        else:
            for habit in self.habits:
                self.write_today(habit)
        lines.end_text()

    def write_today(self, habit: Habit) -> None:
        lines = self.lines
        line = ("row", "checklist")
        done = self.today in habit.done
        lines.link(
            "[x]" if done else "[ ]",
            lambda chosen=habit: self.tick(chosen, self.today),
            "faded" if done else "strong",
            *line,
        )
        lines.write(" ", *line)
        lines.link(
            habit.name,
            lambda chosen=habit: self.tick(chosen, self.today),
            "faded" if done else "body",
            *line,
        )
        lines.write("\t", *line)
        current = streak(habit.done, self.today)
        if current:
            lines.write(streak_text(current), "accent" if done else "muted", *line)
            lines.write("   ", *line)
        if self.confirming == habit.id:
            lines.link("delete?", lambda chosen=habit: self.ask_delete(chosen), "alert", *line)
        else:
            lines.link("x", lambda chosen=habit: self.ask_delete(chosen), "faded", *line)
        lines.write("\n", *line)

    def write_week(self) -> None:
        lines = self.lines
        days = week_days(self.today)
        lines.write(" " * (NAME_CHARS + 1), "faded", "row")
        for day in days:
            lines.write("MTWTFSS"[day.weekday()], "strong" if day == self.today else "faded", "row")
            lines.write(CELL_GAP, "faded", "row")
        lines.write("\n", "row")

        for habit in self.habits:
            line = ("row",)
            lines.write(fit_name(habit.name), "body", *line)
            for day in days:
                if day > self.today:
                    lines.write(FUTURE_CELL, "faded", *line)
                else:
                    done = day in habit.done
                    lines.link(
                        DONE_CELL if done else OPEN_CELL,
                        lambda chosen=habit, when=day: self.tick(chosen, when),
                        *(("strong", "accent") if done else ("faded",)),
                        *line,
                    )
                lines.write(CELL_GAP, *line)
            so_far = [day for day in days if day <= self.today]
            done_count = sum(day in habit.done for day in so_far)
            lines.write(f"\t{done_count} of {len(so_far)}", "strong" if done_count else "faded", *line)
            best = best_streak(habit.done)
            if best:
                lines.write(f"  best {best}", "muted", *line)
            lines.write("\n", *line)

    def destroy(self) -> None:
        cancel_pending_after(self)
        unwatch(self.recolor)
        accent.unwatch(self.recolor)
        if self.reload in HABITS.listeners:
            HABITS.listeners.remove(self.reload)
        if self.render in SETTINGS.listeners:
            SETTINGS.listeners.remove(self.render)
        super().destroy()

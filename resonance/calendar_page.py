from __future__ import annotations

import calendar
import tkinter as tk
import tkinter.font as tkfont
from datetime import date, datetime, time, timedelta

import customtkinter

from .constants import (
    ACCENT,
    BACKGROUND,
    FAINT,
    HOVER,
    INK,
    INK_SOFT,
    MONO_FONT,
    MUTED,
    RULE,
)
from .event_dialog import EventDialog
from .events import (
    Event,
    assign_lanes,
    delete_event,
    events_on,
    load_events,
    save_event,
)
from .theme import color, unwatch, watch
from .windows import cancel_pending_after, outline_width

VIEWS: tuple[str, ...] = ("today", "3 days", "week", "month")
VIEW_DAYS: dict[str, int] = {"today": 1, "3 days": 3, "week": 7}
WEEKDAY_NAMES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

# Unscaled sizes; multiplied by the CTk scaling when drawing.
HOUR_HEIGHT = 40
GUTTER = 50
DAY_LABEL_HEIGHT = 24
ALL_DAY_ROW_HEIGHT = 22
MONTH_LINE_HEIGHT = 17
DEFAULT_FIRST_HOUR = 8


def mono(size: int, weight: str = "normal") -> customtkinter.CTkFont:
    return customtkinter.CTkFont(family=MONO_FONT, size=size, weight=weight)


class CalendarPage(customtkinter.CTkFrame):
    """Hub page with today, 3-day, week and month views of local events.

    Drawn on Tk canvases rather than CTk widgets: a week of hour slots
    would otherwise be hundreds of widgets. Canvases aren't scaled by
    CTk, so every size is multiplied by the widget scaling by hand.
    """

    def __init__(self, hub: customtkinter.CTkToplevel) -> None:
        super().__init__(hub, fg_color="transparent")
        self.hub = hub
        self.events: list[Event] = load_events()
        self.view: str = "week"
        self.anchor: date = date.today()
        self.scroll_to_morning: bool = True
        self.dialog: EventDialog | None = None
        self.fonts: dict[tuple[int, str, float], tkfont.Font] = {}
        # Geometry of the last drawing, used to map clicks to days/times.
        self.layout: dict[str, float] = {}
        self.layout_days: list[date] = []

        nav = customtkinter.CTkFrame(self, fg_color="transparent")
        nav.pack(fill="x")
        self.add_nav_button(nav, "<", lambda: self.step(-1), 34)
        self.add_nav_button(nav, "today", self.go_today, 64)
        self.add_nav_button(nav, ">", lambda: self.step(1), 34)
        self.title_label = customtkinter.CTkLabel(
            nav,
            text="",
            font=mono(14, "bold"),
            text_color=INK,
        )
        self.title_label.pack(side="left", padx=(16, 0))
        self.view_buttons: dict[str, customtkinter.CTkButton] = {}
        for view in reversed(VIEWS):
            button = customtkinter.CTkButton(
                nav,
                text=view,
                width=len(view) * 9 + 18,
                height=28,
                corner_radius=0,
                border_width=0,
                font=mono(11, "bold"),
                command=lambda chosen=view: self.set_view(chosen),
            )
            button.pack(side="right", padx=(6, 0))
            self.view_buttons[view] = button

        self.header_canvas = tk.Canvas(
            self,
            height=1,
            bg=color(BACKGROUND),
            highlightthickness=0,
            bd=0,
        )
        self.header_canvas.pack(fill="x", pady=(16, 0))
        self.body = tk.Frame(self, bg=color(BACKGROUND), bd=0, highlightthickness=0)
        self.body.pack(fill="both", expand=True)
        self.grid_canvas = tk.Canvas(
            self.body,
            bg=color(BACKGROUND),
            highlightthickness=0,
            bd=0,
        )
        self.scrollbar = customtkinter.CTkScrollbar(
            self.body,
            command=self.grid_canvas.yview,
            fg_color=BACKGROUND,
            button_color=HOVER,
            button_hover_color=RULE,
        )
        self.grid_canvas.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side="right", fill="y")
        self.grid_canvas.pack(side="left", fill="both", expand=True)

        self.grid_canvas.bind("<Configure>", lambda _event: self.redraw())
        self.grid_canvas.bind("<Double-Button-1>", self.on_grid_double_click)
        self.grid_canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        self.grid_canvas.bind("<Button-4>", lambda _event: self.scroll(-1))
        self.grid_canvas.bind("<Button-5>", lambda _event: self.scroll(1))
        self.header_canvas.bind(
            "<Double-Button-1>",
            self.on_header_double_click,
        )
        for canvas in (self.grid_canvas, self.header_canvas):
            canvas.tag_bind("event", "<Button-1>", self.on_event_click)
            canvas.tag_bind("goto", "<Button-1>", self.on_goto_click)

        self.set_view(self.view)
        self.after(60_000, self.tick)
        watch(self.retheme)

    def retheme(self) -> None:
        for widget in (self.header_canvas, self.body, self.grid_canvas):
            widget.configure(bg=color(BACKGROUND))
        self.redraw()

    # Navigation

    def add_nav_button(
        self,
        parent: customtkinter.CTkFrame,
        text: str,
        command: object,
        width: int,
    ) -> None:
        customtkinter.CTkButton(
            parent,
            text=text,
            width=width,
            height=28,
            corner_radius=0,
            border_width=outline_width(self),
            border_color=INK,
            fg_color="transparent",
            hover_color=HOVER,
            text_color=INK,
            font=mono(11, "bold"),
            command=command,
        ).pack(side="left", padx=(0, 6))

    def set_view(self, view: str) -> None:
        self.view = view
        for name, button in self.view_buttons.items():
            selected = name == view
            button.configure(
                fg_color=INK if selected else "transparent",
                hover_color=INK_SOFT if selected else HOVER,
                text_color=BACKGROUND if selected else MUTED,
            )
        if view == "month":
            self.scrollbar.pack_forget()
        elif not self.scrollbar.winfo_ismapped():
            self.scrollbar.pack(side="right", fill="y", before=self.grid_canvas)
        self.scroll_to_morning = True
        self.redraw()

    def step(self, direction: int) -> None:
        if self.view == "month":
            month_index = self.anchor.year * 12 + self.anchor.month - 1 + direction
            self.anchor = date(month_index // 12, month_index % 12 + 1, 1)
        else:
            self.anchor += timedelta(days=VIEW_DAYS[self.view] * direction)
        self.redraw()

    def go_today(self) -> None:
        self.anchor = date.today()
        self.scroll_to_morning = True
        self.redraw()

    def show_day(self, day: date) -> None:
        self.anchor = day
        self.set_view("today")

    def visible_days(self) -> list[date]:
        if self.view == "week":
            monday = self.anchor - timedelta(days=self.anchor.weekday())
            return [monday + timedelta(days=offset) for offset in range(7)]
        return [
            self.anchor + timedelta(days=offset)
            for offset in range(VIEW_DAYS[self.view])
        ]

    def title_text(self) -> str:
        if self.view == "month":
            return f"{self.anchor:%B %Y}"
        days = self.visible_days()
        first, last = days[0], days[-1]
        if first == last:
            return f"{first:%A} {first.day} {first:%B %Y}"
        if (first.year, first.month) == (last.year, last.month):
            return f"{first.day} – {last.day} {last:%b %Y}"
        if first.year == last.year:
            return f"{first.day} {first:%b} – {last.day} {last:%b %Y}"
        return f"{first.day} {first:%b %Y} – {last.day} {last:%b %Y}"

    def tick(self) -> None:
        # Moves the "now" line and rolls over at midnight.
        if self.winfo_ismapped():
            self.redraw()
        self.after(60_000, self.tick)

    # Drawing

    def scaling(self) -> float:
        return customtkinter.ScalingTracker.get_widget_scaling(self)

    def font(self, size: int, weight: str = "normal") -> tkfont.Font:
        scaling = self.scaling()
        key = (size, weight, scaling)
        if key not in self.fonts:
            self.fonts[key] = tkfont.Font(
                family=MONO_FONT,
                size=-round(size * scaling),
                weight=weight,
            )
        return self.fonts[key]

    def redraw(self) -> None:
        self.title_label.configure(text=self.title_text())
        if self.grid_canvas.winfo_width() <= 1:
            return
        if self.view == "month":
            self.draw_month()
        else:
            self.draw_time_grid()

    def draw_time_grid(self) -> None:
        s = self.scaling()
        days = self.visible_days()
        header, grid = self.header_canvas, self.grid_canvas
        width = grid.winfo_width()
        gutter = GUTTER * s
        column = (width - gutter) / len(days)
        hour = HOUR_HEIGHT * s
        label_height = DAY_LABEL_HEIGHT * s
        all_day_height = ALL_DAY_ROW_HEIGHT * s
        today = date.today()
        self.layout = {
            "gutter": gutter,
            "column": column,
            "hour": hour,
            "label_height": label_height,
        }
        self.layout_days = days

        header.delete("all")
        header.configure(height=label_height + all_day_height + 4 * s)
        header.create_text(
            gutter - 6 * s,
            label_height + all_day_height / 2 + 1 * s,
            text="all day",
            anchor="e",
            font=self.font(9),
            fill=color(MUTED),
        )
        for index, day in enumerate(days):
            x = gutter + index * column
            tags = ("goto", f"goto:{day.isoformat()}")
            label = f"{day:%a} {day.day}".lower()
            label_color = INK_SOFT
            if day == today:
                half_width = min(
                    column / 2 - 2 * s,
                    self.font(10, "bold").measure(label) / 2 + 12 * s,
                )
                header.create_rectangle(
                    x + column / 2 - half_width,
                    1,
                    x + column / 2 + half_width,
                    label_height - 1,
                    fill=color(INK),
                    outline="",
                    tags=tags,
                )
                label_color = BACKGROUND
            header.create_text(
                x + column / 2,
                label_height / 2,
                text=label,
                font=self.font(10, "bold"),
                fill=color(label_color),
                tags=tags,
            )
            all_day = [event for event in events_on(self.events, day) if event.all_day]
            if all_day:
                extra = f" +{len(all_day) - 1}" if len(all_day) > 1 else ""
                self.draw_event_box(
                    header,
                    all_day[0],
                    (
                        x + 2 * s,
                        label_height + 2 * s,
                        x + column - 2 * s,
                        label_height + all_day_height,
                    ),
                    [all_day[0].title + extra],
                )

        grid.delete("all")
        total_height = 24 * hour
        grid.configure(
            scrollregion=(0, 0, width, total_height),
            yscrollincrement=round(hour / 2),
        )
        for hour_index in range(24):
            y = hour_index * hour
            grid.create_line(gutter, y, width, y, fill=color(RULE))
            grid.create_line(
                gutter,
                y + hour / 2,
                width,
                y + hour / 2,
                fill=color(RULE),
                dash=(2, 4),
            )
            if hour_index:
                grid.create_text(
                    gutter - 6 * s,
                    y,
                    text=f"{hour_index:02d}:00",
                    anchor="e",
                    font=self.font(9),
                    fill=color(MUTED),
                )
        for index in range(len(days) + 1):
            x = gutter + index * column
            grid.create_line(x, 0, x, total_height, fill=color(RULE))

        for index, day in enumerate(days):
            x = gutter + index * column
            timed = [event for event in events_on(self.events, day) if not event.all_day]
            for event, lane, lanes in assign_lanes(timed):
                lane_width = (column - 4 * s) / lanes
                left = x + 2 * s + lane * lane_width
                top = event.start_minutes() / 60 * hour + 1
                bottom = max(top + 18 * s, event.end_minutes() / 60 * hour - 1)
                end = event.end_minutes()
                self.draw_event_box(
                    grid,
                    event,
                    (left, top, left + lane_width - 2 * s, bottom),
                    [
                        event.title,
                        f"{event.start:%H:%M}–{end // 60:02d}:{end % 60:02d}",
                    ],
                )

        if today in days:
            now = datetime.now()
            x = gutter + days.index(today) * column
            y = (now.hour * 60 + now.minute) / 60 * hour
            grid.create_line(
                x,
                y,
                x + column,
                y,
                fill=color(ACCENT),
                width=max(1, round(2 * s)),
            )
            dot = 3 * s
            grid.create_rectangle(
                x - dot,
                y - dot,
                x + dot,
                y + dot,
                fill=color(ACCENT),
                outline="",
            )

        if self.scroll_to_morning:
            self.scroll_to_morning = False
            first_hour = DEFAULT_FIRST_HOUR
            if today in days:
                # Keep the "now" line in view, with a little context above.
                first_hour = max(0, datetime.now().hour - 2)
            grid.yview_moveto(first_hour / 24)

    def draw_month(self) -> None:
        s = self.scaling()
        header, grid = self.header_canvas, self.grid_canvas
        width, height = grid.winfo_width(), grid.winfo_height()
        first = self.anchor.replace(day=1)
        start = first - timedelta(days=first.weekday())
        _, month_days = calendar.monthrange(first.year, first.month)
        rows = (first.weekday() + month_days + 6) // 7
        column, row_height = width / 7, height / rows
        label_height = DAY_LABEL_HEIGHT * s
        line_height = MONTH_LINE_HEIGHT * s
        today = date.today()
        self.layout = {"column": column, "row": row_height}
        self.layout_days = [start + timedelta(days=offset) for offset in range(rows * 7)]

        header.delete("all")
        header.configure(height=label_height)
        for index, name in enumerate(WEEKDAY_NAMES):
            header.create_text(
                index * column + column / 2,
                label_height / 2,
                text=name,
                font=self.font(10, "bold"),
                fill=color(MUTED),
            )

        grid.delete("all")
        grid.configure(scrollregion=(0, 0, width, height))
        grid.yview_moveto(0)
        number_font = self.font(10, "bold")
        event_font = self.font(9)
        char_width = event_font.measure("0")
        for offset, day in enumerate(self.layout_days):
            x = offset % 7 * column
            y = offset // 7 * row_height
            grid.create_rectangle(x, y, x + column, y + row_height, outline=color(RULE))
            number_color = INK_SOFT if day.month == first.month else FAINT
            tags = ("goto", f"goto:{day.isoformat()}")
            if day == today:
                box = number_font.measure("00") + 6 * s
                grid.create_rectangle(
                    x + 3 * s,
                    y + 3 * s,
                    x + 3 * s + box,
                    y + 3 * s + number_font.metrics("linespace"),
                    fill=color(INK),
                    outline="",
                    tags=tags,
                )
                number_color = BACKGROUND
            grid.create_text(
                x + 6 * s,
                y + 3 * s,
                text=str(day.day),
                anchor="nw",
                font=number_font,
                fill=color(number_color),
                tags=tags,
            )

            day_events = events_on(self.events, day)
            capacity = max(0, int((row_height - 24 * s) // line_height))
            shown = day_events
            if len(day_events) > capacity:
                shown = day_events[: max(0, capacity - 1)]
            top = y + 22 * s
            max_chars = max(1, int((column - 12 * s) // char_width))
            for line_index, event in enumerate(shown):
                line_top = top + line_index * line_height
                event_tags = ("event", f"event:{event.id}")
                if event.all_day:
                    grid.create_rectangle(
                        x + 3 * s,
                        line_top,
                        x + column - 3 * s,
                        line_top + line_height - 2 * s,
                        fill=color(HOVER),
                        outline="",
                        tags=event_tags,
                    )
                grid.create_text(
                    x + 6 * s,
                    line_top + 1 * s,
                    text=truncate(event.label(), max_chars),
                    anchor="nw",
                    font=event_font,
                    fill=color(INK),
                    tags=event_tags,
                )
            hidden = len(day_events) - len(shown)
            if hidden:
                grid.create_text(
                    x + 6 * s,
                    top + len(shown) * line_height + 1 * s,
                    text=f"+{hidden} more",
                    anchor="nw",
                    font=event_font,
                    fill=color(MUTED),
                    tags=tags,
                )

    def draw_event_box(
        self,
        canvas: tk.Canvas,
        event: Event,
        box: tuple[float, float, float, float],
        lines: list[str],
    ) -> None:
        s = self.scaling()
        left, top, right, bottom = box
        tags = ("event", f"event:{event.id}")
        canvas.create_rectangle(
            left,
            top,
            right,
            bottom,
            fill=color(HOVER),
            outline=color(INK),
            tags=tags,
        )
        max_chars = int((right - left - 8 * s) // self.font(10).measure("0"))
        y = top + 2 * s
        for index, line in enumerate(lines):
            line_font = self.font(10, "bold" if index == 0 else "normal")
            line_height = line_font.metrics("linespace")
            if max_chars < 1 or (index and y + line_height > bottom):
                break
            canvas.create_text(
                left + 4 * s,
                y,
                text=truncate(line, max_chars),
                anchor="nw",
                font=line_font,
                fill=color(INK if index == 0 else INK_SOFT),
                tags=tags,
            )
            y += line_height

    # Interaction

    def scroll(self, units: int) -> None:
        if self.view != "month":
            self.grid_canvas.yview_scroll(units, "units")

    def on_mouse_wheel(self, event: tk.Event[tk.Misc]) -> None:
        self.scroll(-1 if event.delta > 0 else 1)

    @staticmethod
    def tagged_value(canvas: tk.Canvas, prefix: str) -> str | None:
        for tag in canvas.gettags("current"):
            if tag.startswith(prefix):
                return tag[len(prefix):]
        return None

    def on_event_click(self, event: tk.Event[tk.Canvas]) -> None:
        event_id = self.tagged_value(event.widget, "event:")
        match = next((item for item in self.events if item.id == event_id), None)
        if match is not None:
            self.open_dialog(match.day, match.start, match)

    def on_goto_click(self, event: tk.Event[tk.Canvas]) -> None:
        day = self.tagged_value(event.widget, "goto:")
        if day is not None and not (self.view == "today" and event.widget is self.header_canvas):
            self.show_day(date.fromisoformat(day))

    def on_grid_double_click(self, event: tk.Event[tk.Canvas]) -> None:
        canvas = self.grid_canvas
        if self.tagged_value(canvas, "event:") is not None:
            return
        x, y = canvas.canvasx(event.x), canvas.canvasy(event.y)
        if self.view == "month":
            column = min(6, int(x // self.layout["column"]))
            row = int(y // self.layout["row"])
            index = row * 7 + column
            if 0 <= index < len(self.layout_days):
                self.open_dialog(self.layout_days[index], None)
            return

        if x < self.layout["gutter"]:
            return
        index = min(
            len(self.layout_days) - 1,
            int((x - self.layout["gutter"]) // self.layout["column"]),
        )
        minute = int(y / self.layout["hour"] * 60) // 30 * 30
        minute = max(0, min(23 * 60 + 30, minute))
        self.open_dialog(self.layout_days[index], time(minute // 60, minute % 60))

    def on_header_double_click(self, event: tk.Event[tk.Canvas]) -> None:
        canvas = self.header_canvas
        if self.view == "month" or self.tagged_value(canvas, "event:") is not None:
            return
        if event.y < self.layout["label_height"] or event.x < self.layout["gutter"]:
            return
        index = min(
            len(self.layout_days) - 1,
            int((event.x - self.layout["gutter"]) // self.layout["column"]),
        )
        self.open_dialog(self.layout_days[index], None)

    def open_dialog(
        self,
        day: date,
        start: time | None,
        event: Event | None = None,
    ) -> None:
        # One dialog at a time; a fast double click would otherwise open two.
        if self.dialog is not None and self.dialog.winfo_exists():
            self.dialog.lift()
            return
        self.dialog = EventDialog(
            self.hub,
            day,
            start,
            self.save_event,
            self.delete_event,
            event,
        )

    def save_event(self, event: Event) -> None:
        save_event(event)
        self.events = load_events()
        if self.view != "month" and event.day not in self.visible_days():
            self.anchor = event.day
        elif self.view == "month" and (event.day.year, event.day.month) != (
            self.anchor.year,
            self.anchor.month,
        ):
            self.anchor = event.day
        self.redraw()

    def delete_event(self, event: Event) -> None:
        delete_event(event)
        self.reload()

    def reload(self) -> None:
        """Re-read events, including ones synced from other devices."""
        self.events = load_events()
        self.redraw()

    def destroy(self) -> None:
        unwatch(self.retheme)
        cancel_pending_after(self)
        super().destroy()


def truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max(1, max_chars - 1)] + "…"

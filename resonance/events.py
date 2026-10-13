"""Calendar events stored locally in events.json.

Named ``events`` rather than ``calendar`` to avoid confusion with the
standard library module.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from .paths import DATA_DIR

EVENTS_PATH = DATA_DIR / "events.json"
DEFAULT_DURATION = timedelta(hours=1)
TIME_PATTERN = re.compile(r"^(\d{1,2})(?::?(\d{2}))?$")


@dataclass
class Event:
    title: str
    day: date
    start: time | None = None
    end: time | None = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex)

    @property
    def all_day(self) -> bool:
        return self.start is None

    def start_minutes(self) -> int:
        return minutes(self.start) if self.start else 0

    def end_minutes(self) -> int:
        """End in minutes after midnight; missing ends last an hour."""
        if self.start is None:
            return 24 * 60
        if self.end is None:
            return min(24 * 60, self.start_minutes() + 60)
        return minutes(self.end)

    def label(self) -> str:
        if self.start is None:
            return self.title
        return f"{self.start:%H:%M} {self.title}"

    def to_dict(self) -> dict[str, str | None]:
        return {
            "id": self.id,
            "title": self.title,
            "day": self.day.isoformat(),
            "start": self.start.strftime("%H:%M") if self.start else None,
            "end": self.end.strftime("%H:%M") if self.end else None,
        }

    @classmethod
    def from_dict(cls, data: object) -> Event | None:
        if not isinstance(data, dict):
            return None
        try:
            return cls(
                title=str(data["title"]),
                day=date.fromisoformat(data["day"]),
                start=parse_time(data.get("start") or ""),
                end=parse_time(data.get("end") or ""),
                id=str(data.get("id") or uuid.uuid4().hex),
            )
        except (KeyError, TypeError, ValueError):
            return None


def minutes(value: time) -> int:
    return value.hour * 60 + value.minute


def parse_time(text: str) -> time | None:
    """Parse "9", "930", "9:30" or "21:00"; empty text means no time."""
    text = text.strip()
    if not text:
        return None
    match = TIME_PATTERN.match(text)
    if match is None:
        raise ValueError(f'"{text}" isn\'t a time, try 14:30')
    hour, minute = int(match.group(1)), int(match.group(2) or 0)
    if len(match.group(1)) > 2 or hour > 23 or minute > 59:
        raise ValueError(f'"{text}" isn\'t a time, try 14:30')
    return time(hour, minute)


def parse_day(text: str) -> date:
    """Parse 2026-10-14 or the UK-style 14/10/2026."""
    text = text.strip()
    for date_format in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, date_format).date()
        except ValueError:
            continue
    raise ValueError(f'"{text}" isn\'t a date, try 2026-10-14')


def load_events() -> list[Event]:
    try:
        with EVENTS_PATH.open(encoding="utf-8") as events_file:
            data: object = json.load(events_file)
    except (OSError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    return [event for item in data if (event := Event.from_dict(item))]


def save_events(events: list[Event]) -> None:
    EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with EVENTS_PATH.open("w", encoding="utf-8") as events_file:
        json.dump([event.to_dict() for event in events], events_file, indent=2)


def events_on(events: list[Event], day: date) -> list[Event]:
    """Events on a day: all-day first, then by start time."""
    return sorted(
        (event for event in events if event.day == day),
        key=lambda event: (not event.all_day, event.start_minutes()),
    )


def assign_lanes(timed: list[Event]) -> list[tuple[Event, int, int]]:
    """Place overlapping events side by side.

    Returns (event, lane, lanes in its overlap group) for each event.
    """
    placed: list[tuple[Event, int, int]] = []
    group: list[tuple[Event, int]] = []
    lane_ends: list[int] = []
    group_end = -1

    def close_group() -> None:
        lanes = max((lane for _event, lane in group), default=-1) + 1
        placed.extend((event, lane, lanes) for event, lane in group)

    for event in sorted(timed, key=Event.start_minutes):
        start, end = event.start_minutes(), event.end_minutes()
        if start >= group_end and group:
            close_group()
            group, lane_ends = [], []
        lane = next(
            (index for index, lane_end in enumerate(lane_ends) if lane_end <= start),
            len(lane_ends),
        )
        if lane == len(lane_ends):
            lane_ends.append(end)
        else:
            lane_ends[lane] = end
        group.append((event, lane))
        group_end = max(group_end, end) if group_end > start else end
    if group:
        close_group()
    return placed

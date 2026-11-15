"""Habits: things to do every day, ticked off one day at a time.

Each habit is a record in the synced ``habit`` collection (habits.json):
``{"name", "created_at", "done": ["2026-11-15", ...]}``, the days it was
done as local ISO dates, sorted. No UI code here; the page is
``habits_page.py``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta

from .paths import DATA_DIR
from .store import Collection, now_iso

HABITS = Collection("habit", DATA_DIR / "habits.json")
# Synced: what the header says once every habit is done today. Set with
# the launcher's "habits done <message>".
DONE_MESSAGE_SETTING = "habits_done_message"
DEFAULT_DONE_MESSAGE = "all done today"


@dataclass
class Habit:
    id: str
    name: str
    created_at: str
    done: set[date] = field(default_factory=set)


def parse_days(raw: object) -> set[date]:
    days: set[date] = set()
    if not isinstance(raw, list):
        return days
    for item in raw:
        try:
            days.add(date.fromisoformat(str(item)))
        except ValueError:
            continue
    return days


def load_habits() -> list[Habit]:
    habits = [
        Habit(
            id=habit_id,
            name=str(data.get("name", "")),
            created_at=str(data.get("created_at", "")),
            done=parse_days(data.get("done")),
        )
        for habit_id, data in HABITS.items()
    ]
    return sorted(habits, key=lambda habit: habit.created_at)


def save_habit(habit: Habit) -> None:
    HABITS.put(
        habit.id,
        {
            "name": habit.name,
            "created_at": habit.created_at,
            "done": sorted(day.isoformat() for day in habit.done),
        },
    )


def add_habit(name: str) -> Habit | None:
    name = name.strip()
    if not name:
        return None
    habit = Habit(uuid.uuid4().hex, name, now_iso())
    save_habit(habit)
    return habit


def delete_habit(habit: Habit) -> None:
    HABITS.delete(habit.id)


def toggle_day(habit: Habit, day: date) -> bool:
    """Tick or untick one day and save. True if it's now done."""
    if day in habit.done:
        habit.done.discard(day)
    else:
        habit.done.add(day)
    save_habit(habit)
    return day in habit.done


def streak(done: set[date], today: date) -> int:
    """Days in a row up to today. Today not being done yet doesn't break
    the streak; it counts from yesterday until the day is over."""
    day = today if today in done else today - timedelta(days=1)
    count = 0
    while day in done:
        count += 1
        day -= timedelta(days=1)
    return count


def best_streak(done: set[date]) -> int:
    best = run = 0
    previous: date | None = None
    for day in sorted(done):
        run = run + 1 if previous is not None and day - previous == timedelta(days=1) else 1
        best = max(best, run)
        previous = day
    return best


def week_days(today: date) -> list[date]:
    """Monday to Sunday of the week ``today`` is in."""
    monday = today - timedelta(days=today.weekday())
    return [monday + timedelta(days=offset) for offset in range(7)]

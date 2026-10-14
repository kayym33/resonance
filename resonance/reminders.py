"""When calendar events are due a reminder. No UI code; see notify.py."""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta

from .events import Event

# The menu of choices in the event dialog, cycled in this order.
REMIND_CHOICES: tuple[int | None, ...] = (None, 0, 5, 10, 15, 30, 60)
# Still remind if the app was asleep or closed through the reminder time,
# as long as the event hasn't been going for longer than this.
LATE_GRACE = timedelta(minutes=2)


def remind_label(remind: int | None) -> str:
    if remind is None:
        return "off"
    if remind == 0:
        return "at start"
    if remind % 60 == 0:
        hours = remind // 60
        return f"{hours} hour{'s' if hours > 1 else ''} before"
    return f"{remind} min before"


def reminder_key(event: Event) -> str:
    """Changes when the event moves, so a moved event reminds again."""
    return f"{event.day.isoformat()}|{event.id}|{event.start}|{event.remind}"


def due_reminders(
    events: list[Event],
    now: datetime,
    sent: set[str],
) -> list[Event]:
    """Timed events whose reminder time has come and not been sent yet.

    All-day events don't remind; the today briefing covers them.
    """
    due: list[Event] = []
    for event in events:
        if event.start is None or event.remind is None:
            continue
        starts = datetime.combine(event.day, event.start)
        if starts - timedelta(minutes=event.remind) <= now < starts + LATE_GRACE:
            if reminder_key(event) not in sent:
                due.append(event)
    return sorted(due, key=lambda event: (event.day, event.start_minutes()))


def reminder_text(event: Event, now: datetime) -> tuple[str, str]:
    """A notification's (title, body), like ("standup", "in 10 min · 09:30–09:45")."""
    assert event.start is not None
    starts = datetime.combine(event.day, event.start)
    minutes_left = math.ceil((starts - now).total_seconds() / 60)
    if minutes_left <= 0:
        when = "now"
    elif minutes_left >= 60 and minutes_left % 60 == 0:
        hours = minutes_left // 60
        when = f"in {hours} hour{'s' if hours > 1 else ''}"
    else:
        when = f"in {minutes_left} min"
    span = f"{event.start:%H:%M}"
    if event.end is not None:
        span += f"–{event.end:%H:%M}"
    return event.title, f"{when} · {span}"


def prune_sent(sent: set[str], today: date) -> set[str]:
    """Forget reminders for days before yesterday."""
    oldest = (today - timedelta(days=1)).isoformat()
    return {key for key in sent if key.split("|", 1)[0] >= oldest}

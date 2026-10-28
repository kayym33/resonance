// When events are due a reminder, for the reminders function. A port of
// resonance/reminders.py. Plain JavaScript with no imports, so
// phone/tests/reminders.mjs can test it with Node.
//
// Events store local dates and times ("2026-10-25", "09:30"), so times
// are compared as "naive" milliseconds: the local wall-clock time
// written as if it were UTC.

export const DEFAULT_REMIND = 10;
// Still remind this long after the reminder time, as on the desktop.
export const LATE_GRACE_MS = 2 * 60 * 1000;

// The wall-clock time in a time zone, as naive milliseconds.
export function localNow(date, timeZone) {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("en-CA", {
      timeZone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hourCycle: "h23",
    }).formatToParts(date).map((part) => [part.type, part.value]),
  );
  return Date.UTC(
    Number(parts.year), Number(parts.month) - 1, Number(parts.day),
    Number(parts.hour), Number(parts.minute), Number(parts.second),
  );
}

export function naive(day, time) {
  const [year, month, date] = day.split("-").map(Number);
  const [hours, minutes] = time.split(":").map(Number);
  return Date.UTC(year, month - 1, date, hours, minutes);
}

// The local day of a naive time, and the days either side: the only
// events that can be due.
export function nearbyDays(nowNaive) {
  return [-1, 0, 1].map((offset) => new Date(nowNaive + offset * 86400000).toISOString().slice(0, 10));
}

function remindOf(data) {
  if (!("remind" in data)) return DEFAULT_REMIND;
  const remind = data.remind;
  if (remind === null) return null;
  return Number.isInteger(remind) && remind >= 0 ? remind : DEFAULT_REMIND;
}

// Changes when the event moves, so a moved event reminds again.
export function reminderKey(id, data) {
  return `${data.day}|${id}|${data.start}|${remindOf(data)}`;
}

// Timed events whose reminder time has come; [{id, data, key}], soonest
// first. All-day events don't remind.
export function dueReminders(rows, nowNaive) {
  const due = [];
  for (const { id, data } of rows) {
    if (!data || typeof data.title !== "string" || typeof data.day !== "string") continue;
    if (typeof data.start !== "string" || !/^\d{1,2}:\d{2}$/.test(data.start)) continue;
    const remind = remindOf(data);
    if (remind === null) continue;
    const starts = naive(data.day, data.start);
    if (starts - remind * 60000 <= nowNaive && nowNaive < starts + LATE_GRACE_MS) {
      due.push({ id, data, key: reminderKey(id, data), starts });
    }
  }
  return due.sort((a, b) => a.starts - b.starts);
}

const pad = (value) => String(value).padStart(2, "0");
const clock = (time) => {
  const [hours, minutes] = time.split(":").map(Number);
  return `${pad(hours)}:${pad(minutes)}`;
};

// Like ("standup", "in 10 min · 09:30–09:45"), as on the desktop.
export function reminderText(data, nowNaive) {
  const minutesLeft = Math.ceil((naive(data.day, data.start) - nowNaive) / 60000);
  let when;
  if (minutesLeft <= 0) when = "now";
  else if (minutesLeft >= 60 && minutesLeft % 60 === 0) {
    const hours = minutesLeft / 60;
    when = `in ${hours} hour${hours > 1 ? "s" : ""}`;
  } else when = `in ${minutesLeft} min`;
  let span = clock(data.start);
  if (typeof data.end === "string" && data.end) span += `–${clock(data.end)}`;
  return { title: data.title, body: `${when} · ${span}` };
}

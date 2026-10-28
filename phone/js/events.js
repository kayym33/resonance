// Calendar events, stored like resonance/events.py: {title, day, start,
// end, remind}, with day as 2026-10-14 and times as 14:30 in local time.

export const DEFAULT_REMIND = 10;
// The same choices as the desktop's event dialog (reminders.py).
export const REMIND_CHOICES = [null, 0, 5, 10, 15, 30, 60];

export function eventFromData(id, data) {
  if (!data || typeof data.title !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(data.day ?? "")) return null;
  const time = (value) => (typeof value === "string" && /^\d{1,2}:\d{2}$/.test(value) ? value.padStart(5, "0") : null);
  let remind = "remind" in data ? data.remind : DEFAULT_REMIND;
  if (remind !== null && !(Number.isInteger(remind) && remind >= 0)) remind = DEFAULT_REMIND;
  return { id, title: data.title, day: data.day, start: time(data.start), end: time(data.end), remind };
}

export function eventData(event) {
  return { title: event.title, day: event.day, start: event.start, end: event.end, remind: event.remind };
}

export function remindLabel(remind) {
  if (remind === null) return "off";
  if (remind === 0) return "at start";
  if (remind % 60 === 0) {
    const hours = remind / 60;
    return `${hours} hour${hours > 1 ? "s" : ""} before`;
  }
  return `${remind} min before`;
}

// Local dates as 2026-10-14, the stored form.
export function isoDay(date) {
  const pad = (value) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

export function dayFromIso(day) {
  const [year, month, date] = day.split("-").map(Number);
  return new Date(year, month - 1, date);
}

export function addDays(day, count) {
  const date = dayFromIso(day);
  date.setDate(date.getDate() + count);
  return isoDay(date);
}

export function minutesOf(time) {
  const [hours, minutes] = time.split(":").map(Number);
  return hours * 60 + minutes;
}

// All-day first, then by start time.
export function sortEvents(events) {
  return [...events].sort(
    (a, b) => a.day.localeCompare(b.day)
      || (a.start === null ? -1 : 0) - (b.start === null ? -1 : 0)
      || (a.start ? minutesOf(a.start) : 0) - (b.start ? minutesOf(b.start) : 0),
  );
}

export function eventSpan(event) {
  if (!event.start) return "all day";
  return event.end ? `${event.start}–${event.end}` : event.start;
}

// "today", "tomorrow", or "sat 31 oct".
export function dayLabel(day, today) {
  if (day === today) return "today";
  if (day === addDays(today, 1)) return "tomorrow";
  const date = dayFromIso(day);
  const weekday = date.toLocaleString("en-GB", { weekday: "short" });
  const month = date.toLocaleString("en-GB", { month: "short" });
  return `${weekday} ${date.getDate()} ${month}`.toLowerCase();
}

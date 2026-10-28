// Tests the reminder timing the server uses (supabase/functions/_shared),
// including time zones. Run from the repo root: node phone/tests/reminders.mjs
import { dueReminders, localNow, naive, nearbyDays, reminderText } from "../../supabase/functions/_shared/reminders.js";

let failures = 0;
function check(ok, name) {
  console.log(`${ok ? "ok  " : "FAIL"} ${name}`);
  if (!ok) failures += 1;
}

const events = [
  { id: "standup", data: { title: "standup", day: "2026-10-26", start: "09:30", end: "09:45", remind: 10 } },
  { id: "lunch", data: { title: "lunch", day: "2026-10-26", start: "12:00", end: null } }, // default 10
  { id: "off", data: { title: "quiet", day: "2026-10-26", start: "09:30", remind: null } },
  { id: "allday", data: { title: "holiday", day: "2026-10-26", start: null } },
  { id: "hour", data: { title: "flight", day: "2026-10-26", start: "11:00", remind: 60 } },
  { id: "broken", data: { title: "broken", day: "2026-10-26", start: "soon" } },
];
const at = (time) => naive("2026-10-26", time);
const ids = (time) => dueReminders(events, at(time)).map((due) => due.id);

check(ids("09:19").length === 0, "nothing due before the reminder time");
check(JSON.stringify(ids("09:20")) === '["standup"]', "due exactly at the reminder time");
check(JSON.stringify(ids("09:31")) === '["standup"]', "still due just after the start (late grace)");
check(ids("09:32").length === 0, "not due two minutes after the start");
check(JSON.stringify(ids("11:50")) === '["lunch"]', "a missing remind means the default 10 minutes");
check(JSON.stringify(ids("10:00")) === '["hour"]', "an hour's notice");
check(!ids("09:25").includes("off") && !ids("09:25").includes("allday"), "off and all-day events don't remind");

const text = reminderText(events[0].data, at("09:20"));
check(text.title === "standup" && text.body === "in 10 min · 09:30–09:45", `reminder text: ${text.body}`);
check(reminderText(events[4].data, at("10:00")).body === "in 1 hour · 11:00", "whole hours read as hours");
check(reminderText(events[1].data, at("12:00")).body === "now · 12:00", "at the start says now");

// 08:20 UTC on 26 Oct 2026 is 08:20 in London (GMT, after the clocks go
// back on the 25th) and 17:20 in Tokyo.
const instant = new Date(Date.UTC(2026, 9, 26, 8, 20));
check(localNow(instant, "Europe/London") === at("08:20"), "London wall-clock time");
check(localNow(instant, "Asia/Tokyo") === at("17:20"), "Tokyo wall-clock time");
check(localNow(new Date(Date.UTC(2026, 6, 1, 8, 20)), "Europe/London") === naive("2026-07-01", "09:20"), "summer time");
check(JSON.stringify(nearbyDays(at("00:10"))) === '["2026-10-25","2026-10-26","2026-10-27"]', "nearby days");

console.log(failures ? `${failures} failed` : "all passed");
process.exit(failures ? 1 : 0);

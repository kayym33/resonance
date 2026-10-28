// Today: the date, what's left, what's coming up and the first to-dos,
// like the desktop's today briefing.
import { addDays, dayLabel, eventSpan } from "../events.js";
import { action, esc, heading, longDate, today } from "../ui.js";
import { addTaskForm, EMPTY, taskRows } from "./todo.js";

// To-dos shown here before "see all".
const TODAY_TASKS = 6;

export function render(ctx) {
  const day = today();
  const tasks = ctx.data.tasks();
  const left = tasks.filter((task) => !task.done);
  const events = ctx.data.events().filter((event) => event.day >= day && event.day <= addDays(day, 1));
  const todays = events.filter((event) => event.day === day);
  const briefing = [
    `${left.length} to-do${left.length === 1 ? "" : "s"} left`,
    todays.length
      ? todays.map((event) => (event.start ? `${event.start} ${event.title}` : event.title)).join(", ")
      : "nothing on today",
  ];
  const name = ctx.data.displayName();
  const upcoming = [day, addDays(day, 1)].map((date) => {
    const list = events.filter((event) => event.day === date);
    if (!list.length) return "";
    return `<h3>${esc(dayLabel(date, day))}</h3><ul class="events">${list.map((event) => `
      <li ${action("go", { to: `/cal/${event.id}` })}>
        <span class="span">${esc(eventSpan(event))}</span><span>${esc(event.title)}</span>
      </li>`).join("")}</ul>`;
  }).join("");
  return {
    crumbs: [],
    html: `
      <p class="today"><span class="label">today</span> <strong>${esc(longDate())}</strong></p>
      ${name ? `<p class="muted">hi ${esc(name)} ~</p>` : ""}
      <p class="briefing">${briefing.map(esc).join("  ·  ")}</p>
      ${heading("up next")}
      ${upcoming || `<p class="muted">nothing today or tomorrow</p>`}
      ${heading("to do")}
      ${addTaskForm()}
      ${tasks.length ? "" : EMPTY}
      <ul class="tasks">${taskRows(left.slice(0, TODAY_TASKS))}</ul>
      ${left.length > TODAY_TASKS || tasks.length > left.length
        ? `<p><a href="#/todo" class="more">all to-dos -></a></p>`
        : ""}`,
  };
}

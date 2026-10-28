// Calendar: an agenda of the coming weeks, and the event editor. Times
// are local, as the desktop stores them; reminders come from the server.
import { addDays, dayLabel, DEFAULT_REMIND, eventSpan, minutesOf, REMIND_CHOICES, remindLabel } from "../events.js";
import { action, button, esc, heading, today, uuid } from "../ui.js";

const AGENDA_DAYS = 30;
let agendaStart = null;

export function render(ctx) {
  const day = today();
  agendaStart ??= day;
  const end = addDays(agendaStart, AGENDA_DAYS - 1);
  const events = ctx.data.events().filter((event) => event.day >= agendaStart && event.day <= end);
  const days = [...new Set(events.map((event) => event.day))];
  const agenda = days.map((date) => `
    <h3${date === day ? ' class="now"' : ""}>${esc(dayLabel(date, day))}</h3>
    <ul class="events">${events.filter((event) => event.day === date).map((event) => `
      <li ${action("go", { to: `/cal/${event.id}` })}>
        <span class="span">${esc(eventSpan(event))}</span><span>${esc(event.title)}</span>
        ${event.start && event.remind !== null ? `<span class="faint">${esc(remindLabel(event.remind))}</span>` : ""}
      </li>`).join("")}</ul>`).join("");
  return {
    crumbs: ["calendar"],
    html: `
      <div class="row-buttons">
        ${button("<", "cal-shift", { by: -AGENDA_DAYS })}
        ${agendaStart === day ? "" : button("today", "cal-today")}
        ${button(">", "cal-shift", { by: AGENDA_DAYS })}
        <span class="spacer"></span>
        ${button("+ event", "go", { to: "/cal/new" }, { solid: true })}
      </div>
      <p class="muted">${esc(dayLabel(agendaStart, day))} to ${esc(dayLabel(end, day))}</p>
      ${agenda || `<pre class="art">  .---------.\n  |  ~ ~ ~  |\n  '---------'\n  nothing on</pre>`}`,
  };
}

export function renderEditor(ctx, { id }) {
  const isNew = id === "new";
  const event = isNew
    ? { id: uuid(), title: "", day: today(), start: null, end: null, remind: DEFAULT_REMIND }
    : ctx.data.event(id);
  if (!event) return { crumbs: ["calendar", "gone"], html: `<p class="muted">that event was deleted</p>` };
  const remindOptions = REMIND_CHOICES.map((choice) => `
    <option value="${choice ?? "off"}"${choice === event.remind ? " selected" : ""}>${esc(remindLabel(choice))}</option>`).join("");
  return {
    crumbs: ["calendar", isNew ? "new event" : event.title],
    html: `
      <form class="editor" data-form="event-save" data-id="${esc(event.id)}">
        <label>title<input name="title" value="${esc(event.title)}" required autocomplete="off"></label>
        <label>day<input name="day" type="date" value="${esc(event.day)}" required></label>
        <div class="pair">
          <label>start<input name="start" type="time" value="${esc(event.start ?? "")}"></label>
          <label>end<input name="end" type="time" value="${esc(event.end ?? "")}"></label>
        </div>
        <p class="hint">leave the start empty for an all-day event</p>
        <label>remind<select name="remind">${remindOptions}</select></label>
        <p class="error" hidden></p>
        <div class="row-buttons">
          <button type="submit" class="button solid">save</button>
          ${button("cancel", "go", { to: "/cal" })}
          <span class="spacer"></span>
          ${isNew ? "" : button("delete", "event-delete", { id: event.id })}
        </div>
      </form>`,
  };
}

export const actions = {
  "cal-shift"(ctx, { by }) {
    agendaStart = addDays(agendaStart ?? today(), Number(by));
    ctx.render();
  },
  "cal-today"(ctx) {
    agendaStart = today();
    ctx.render();
  },
  "event-delete"(ctx, { id }) {
    if (!confirm("delete this event?")) return;
    ctx.data.deleteEvent(id);
    ctx.go("/cal");
  },
};

export const forms = {
  "event-save"(ctx, form) {
    const fields = form.elements;
    const start = fields.start.value || null;
    const end = start ? fields.end.value || null : null;
    const error = form.querySelector(".error");
    if (end && minutesOf(end) <= minutesOf(start)) {
      error.textContent = "the end has to be after the start";
      error.hidden = false;
      return;
    }
    const remind = fields.remind.value === "off" ? null : Number(fields.remind.value);
    ctx.data.saveEvent({
      id: form.dataset.id,
      title: fields.title.value.trim(),
      day: fields.day.value,
      start,
      end,
      remind,
    });
    ctx.go("/cal");
  },
};

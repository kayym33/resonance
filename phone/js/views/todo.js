// To-dos: on today (the first few) and in full, with done ones apart.
import { action, button, esc, heading } from "../ui.js";

// The task being edited, and what's typed so far: {id, text}, or null.
// Kept here rather than in the page, because synced changes re-render it
// (app.js puts the focus and the typed text back).
let editing = null;

// Swipe a row right to tick it (or untick), left to delete it; the
// buttons do the same for a tap. Tapping the text edits it.
export function taskRows(tasks) {
  return tasks.map((task) => editing?.id === task.id ? editRow(task) : `
    <li class="task${task.done ? " done" : ""}" data-id="${esc(task.id)}"
      data-swipe-right="todo-toggle" data-right-label="${task.done ? "[ ] undo" : "[x] done"}"
      data-swipe-left="todo-delete" data-left-label="delete">
      <div class="slide">
        <button type="button" class="check" ${action("todo-toggle", { id: task.id })} aria-label="${task.done ? "not done" : "done"}">${task.done ? "[x]" : "[ ]"}</button>
        <span class="task-text" role="button" tabindex="0" ${action("todo-edit", { id: task.id })}>${esc(task.text)}</span>
        <button type="button" class="delete" ${action("todo-delete", { id: task.id })} aria-label="delete">x</button>
      </div>
    </li>`).join("");
}

// No swipes while editing, so dragging in the field moves the cursor.
function editRow(task) {
  return `
    <li class="task editing${task.done ? " done" : ""}" data-id="${esc(task.id)}">
      <div class="slide">
        <button type="button" class="check" ${action("todo-toggle", { id: task.id })} aria-label="${task.done ? "not done" : "done"}">${task.done ? "[x]" : "[ ]"}</button>
        <form class="edit" data-form="todo-edit">
          <input name="text" value="${esc(editing.text)}" aria-label="edit task" autocomplete="off"
            enterkeyhint="done" data-input="todo-edit" data-blur="todo-edit" data-cancel="todo-edit-cancel">
        </form>
        <button type="button" class="delete" ${action("todo-delete", { id: task.id })} aria-label="delete">x</button>
      </div>
    </li>`;
}

export function addTaskForm() {
  return `
    <form class="add" data-form="todo-add">
      <input name="text" placeholder="+ add a task" autocomplete="off" enterkeyhint="done">
    </form>`;
}

export const EMPTY = `<pre class="art">  [x] [x] [x]\n   all done ~</pre>`;

export function render(ctx) {
  const tasks = ctx.data.tasks();
  const todo = tasks.filter((task) => !task.done);
  const done = tasks.filter((task) => task.done);
  const count = tasks.length ? `${todo.length} left${done.length ? ` · ${done.length} done` : ""}` : "";
  return {
    crumbs: ["to-do"],
    html: `
      <div class="section-head">${heading("to do")}<span class="muted">${esc(count)}</span>
        ${done.length ? button("clear done", "todo-clear", {}, { small: true }) : ""}</div>
      ${addTaskForm()}
      ${tasks.length ? "" : EMPTY}
      <ul class="tasks">${taskRows(todo)}</ul>
      ${done.length ? `${heading("done")}<ul class="tasks">${taskRows(done)}</ul>` : ""}`,
  };
}

// Ends the edit. Empty or unchanged text leaves the task as it was. The
// task is read afresh, since it may have been ticked meanwhile. Saving
// re-renders through the store; otherwise this does.
export function finishEdit(ctx, save = true) {
  if (!editing) return;
  const { id, text } = editing;
  editing = null;
  const task = ctx.data.tasks().find((item) => item.id === id);
  const trimmed = text.trim();
  if (save && task && trimmed && trimmed !== task.text) ctx.data.saveTask({ ...task, text: trimmed });
  else ctx.render();
}

export const actions = {
  "todo-toggle"(ctx, { id }) {
    const task = ctx.data.tasks().find((item) => item.id === id);
    if (task) ctx.data.saveTask({ ...task, done: !task.done });
  },
  "todo-delete"(ctx, { id }) {
    if (editing?.id === id) editing = null;
    ctx.data.deleteTask(id);
  },
  "todo-clear"(ctx) {
    finishEdit(ctx);
    for (const task of ctx.data.tasks()) if (task.done) ctx.data.deleteTask(task.id);
  },
  "todo-edit"(ctx, { id }) {
    const task = ctx.data.tasks().find((item) => item.id === id);
    if (!task) return;
    if (editing) finishEdit(ctx);
    editing = { id, text: task.text };
    ctx.render();
    // Focused during the tap, or iOS won't bring up the keyboard.
    const field = document.querySelector('[data-input="todo-edit"]');
    if (field) {
      field.focus({ preventScroll: true });
      field.setSelectionRange(field.value.length, field.value.length);
    }
  },
  "todo-edit-cancel"(ctx) {
    finishEdit(ctx, false);
  },
};

export const forms = {
  "todo-add"(ctx, form) {
    // Cleared first: adding re-renders the list and keeps this box focused.
    const text = form.elements.text.value;
    form.elements.text.value = "";
    ctx.data.addTask(text);
  },
  "todo-edit"(ctx) {
    finishEdit(ctx);
  },
};

export const inputs = {
  "todo-edit"(_ctx, field) {
    if (editing) editing.text = field.value;
  },
};

// Tapping anywhere else, or iOS's "done" above the keyboard, saves.
export const blurs = {
  "todo-edit"(ctx) {
    // A re-render puts the focus straight back in the new field.
    if (document.activeElement?.dataset?.input === "todo-edit") return;
    finishEdit(ctx);
  },
};

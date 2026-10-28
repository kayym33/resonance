// To-dos: on today (the first few) and in full, with done ones apart.
import { action, button, esc, heading } from "../ui.js";

// Swipe a row right to tick it (or untick), left to delete it; the
// buttons do the same for a tap.
export function taskRows(tasks) {
  return tasks.map((task) => `
    <li class="task${task.done ? " done" : ""}" data-id="${esc(task.id)}"
      data-swipe-right="todo-toggle" data-right-label="${task.done ? "[ ] undo" : "[x] done"}"
      data-swipe-left="todo-delete" data-left-label="delete">
      <div class="slide">
        <button type="button" class="check" ${action("todo-toggle", { id: task.id })} aria-label="${task.done ? "not done" : "done"}">${task.done ? "[x]" : "[ ]"}</button>
        <span class="task-text">${esc(task.text)}</span>
        <button type="button" class="delete" ${action("todo-delete", { id: task.id })} aria-label="delete">x</button>
      </div>
    </li>`).join("");
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

export const actions = {
  "todo-toggle"(ctx, { id }) {
    const task = ctx.data.tasks().find((item) => item.id === id);
    if (task) ctx.data.saveTask({ ...task, done: !task.done });
  },
  "todo-delete"(ctx, { id }) {
    ctx.data.deleteTask(id);
  },
  "todo-clear"(ctx) {
    for (const task of ctx.data.tasks()) if (task.done) ctx.data.deleteTask(task.id);
  },
};

export const forms = {
  "todo-add"(ctx, form) {
    // Cleared first: adding re-renders the list and keeps this box focused.
    const text = form.elements.text.value;
    form.elements.text.value = "";
    ctx.data.addTask(text);
  },
};

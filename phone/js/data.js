// Typed access to the synced records, in the same shapes the desktop
// writes (todo.py, events.py, recipes.py, settings.py, user_profile.py).
import { eventData, eventFromData, sortEvents } from "./events.js";
import { recipeData, recipeFromData } from "./recipes.js";
import { nowIso } from "./store.js";
import { uuid } from "./ui.js";

export class Data {
  constructor(store) {
    this.store = store;
  }

  // To-dos, oldest first like the desktop.
  tasks() {
    return this.store.items("task")
      .map(([id, data]) => ({ id, text: String(data.text ?? ""), done: Boolean(data.done), created_at: String(data.created_at ?? "") }))
      .sort((a, b) => (a.created_at < b.created_at ? -1 : a.created_at > b.created_at ? 1 : 0));
  }

  addTask(text) {
    text = text.trim();
    if (text) this.store.put("task", uuid(), { text, done: false, created_at: nowIso() });
  }

  saveTask(task) {
    this.store.put("task", task.id, { text: task.text, done: task.done, created_at: task.created_at });
  }

  deleteTask(id) {
    this.store.remove("task", id);
  }

  events() {
    return sortEvents(
      this.store.items("event").map(([id, data]) => eventFromData(id, data)).filter(Boolean),
    );
  }

  event(id) {
    const data = this.store.get("event", id);
    return data ? eventFromData(id, data) : null;
  }

  saveEvent(event) {
    this.store.put("event", event.id, eventData(event));
  }

  deleteEvent(id) {
    this.store.remove("event", id);
  }

  recipes() {
    return this.store.items("recipe")
      .map(([id, data]) => recipeFromData(id, data))
      .sort((a, b) => a.title.toLowerCase().localeCompare(b.title.toLowerCase()));
  }

  recipe(id) {
    const data = this.store.get("recipe", id);
    return data ? recipeFromData(id, data) : null;
  }

  saveRecipe(recipe) {
    this.store.put("recipe", recipe.id, recipeData(recipe));
  }

  deleteRecipe(id) {
    this.store.remove("recipe", id);
  }

  setting(key) {
    return this.store.get("setting", key)?.value ?? null;
  }

  saveSetting(key, value) {
    if (value === null) this.store.remove("setting", key);
    else this.store.put("setting", key, { value });
  }

  displayName() {
    return String(this.store.get("profile", "me")?.display_name ?? "").trim();
  }
}

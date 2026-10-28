// Cooking timers. iOS pauses a home-screen app as soon as it's in the
// background, so each timer also asks the server to push a notification
// when it ends (scheduled_pushes); the countdown on screen is for while
// the app is open. Timers are saved, so they survive the app closing.
import { shorten, uuid } from "./ui.js";

const TIMERS_KEY = "t1ld3.timers";
// A finished timer stays on screen this long, then clears itself.
const DONE_LINGER_MS = 5 * 60 * 1000;

export function formatClock(seconds) {
  seconds = Math.max(0, Math.round(seconds));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const rest = String(seconds % 60).padStart(2, "0");
  return hours ? `${hours}:${String(minutes).padStart(2, "0")}:${rest}` : `${String(minutes).padStart(2, "0")}:${rest}`;
}

export class Timers {
  constructor(cloud) {
    this.cloud = cloud;
    try {
      this.list = JSON.parse(localStorage.getItem(TIMERS_KEY)) ?? [];
    } catch {
      this.list = [];
    }
    this.listeners = [];
    setInterval(() => this.tick(), 1000);
  }

  save() {
    localStorage.setItem(TIMERS_KEY, JSON.stringify(this.list));
  }

  start(recipe, stepNumber, step, seconds) {
    const timer = {
      id: uuid(),
      recipeId: recipe.id,
      recipeTitle: recipe.title,
      stepNumber,
      step,
      endsAt: Date.now() + seconds * 1000,
      doneAt: null,
    };
    this.list.push(timer);
    this.save();
    this.changed();
    if (this.cloud.signedIn) {
      this.cloud
        .schedulePush(timer.id, timer.endsAt, `${recipe.title}: timer done`, `step ${stepNumber}: ${shorten(step, 80)}`)
        .catch(() => {});
    }
    return timer;
  }

  running(recipeId, stepNumber) {
    return this.list.some((timer) => timer.recipeId === recipeId && timer.stepNumber === stepNumber && !timer.doneAt);
  }

  dismiss(id) {
    const timer = this.list.find((item) => item.id === id);
    this.list = this.list.filter((item) => item.id !== id);
    this.save();
    this.changed();
    if (timer && !timer.doneAt && this.cloud.signedIn) this.cloud.cancelPush(id).catch(() => {});
  }

  tick() {
    const now = Date.now();
    let changed = false;
    for (const timer of this.list) {
      if (!timer.doneAt && now >= timer.endsAt) {
        timer.doneAt = now;
        changed = true;
      }
    }
    const kept = this.list.filter((timer) => !timer.doneAt || now - timer.doneAt < DONE_LINGER_MS);
    if (kept.length !== this.list.length) {
      this.list = kept;
      changed = true;
    }
    if (changed) this.save();
    if (this.list.length) this.changed();
  }

  changed() {
    for (const listener of this.listeners) listener();
  }

  // One line per timer, for the strip above every view.
  lines() {
    const now = Date.now();
    return this.list.map((timer) => ({
      id: timer.id,
      done: Boolean(timer.doneAt),
      clock: timer.doneAt ? "done!" : formatClock((timer.endsAt - now) / 1000),
      label: `${timer.recipeTitle} · step ${timer.stepNumber}`,
    }));
  }
}

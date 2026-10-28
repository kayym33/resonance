// t1ld3 on the phone: routing, rendering and the pieces every view shares
// (header trail, tab bar, timer strip). Views live in views/; each returns
// {crumbs, html} and lists its actions, forms, inputs and swipes, which
// the handlers here dispatch to by name (data-action="todo-toggle").
import { Cloud } from "./cloud.js";
import { Data } from "./data.js";
import { Store, SyncEngine } from "./store.js";
import { Timers } from "./timers.js";
import { esc } from "./ui.js";
import * as calendar from "./views/calendar.js";
import * as cookbook from "./views/cookbook.js";
import * as me from "./views/me.js";
import * as today from "./views/today.js";
import * as todo from "./views/todo.js";

const SYNC_INTERVAL_MS = 60 * 1000;
const FLASH_MS = 4000;
const NOISE = " .:;'`~*+-,";

const cloud = new Cloud();
const store = new Store();
const sync = new SyncEngine(store, cloud);
const data = new Data(store);
const timers = new Timers(cloud);
const main = document.querySelector("main");

// [pattern, view name, render, tab]. Views without a tab show none lit.
const ROUTES = [
  [/^\/$/, "today", today.render, "/"],
  [/^\/todo$/, "todo", todo.render, "/todo"],
  [/^\/cal$/, "calendar", calendar.render, "/cal"],
  [/^\/cal\/(?<id>[\w-]+)$/, "event", calendar.renderEditor, "/cal"],
  [/^\/cook$/, "cookbook", cookbook.renderHome, "/cook"],
  [/^\/cook\/(?<id>[\w-]+)\/edit$/, "recipe-edit", cookbook.renderEditor, "/cook"],
  [/^\/cook\/(?<id>[\w-]+)\/cooking$/, "cooking", cookbook.renderCooking, "/cook"],
  [/^\/cook\/(?<id>[\w-]+)$/, "recipe", cookbook.renderRecipe, "/cook"],
  [/^\/me$/, "me", me.render, "/me"],
];
// Where a first crumb that's just a name leads.
const TAB_ROOTS = { "to-do": "/todo", calendar: "/cal", cookbook: "/cook", me: "/me" };
// Typing in these would be lost if synced changes re-rendered them.
const EDITORS = new Set(["event", "recipe-edit"]);
const VIEWS = [today, todo, calendar, cookbook, me];
const handlers = (kind) => Object.assign({}, ...VIEWS.map((view) => view[kind] ?? {}));
const ACTIONS = handlers("actions");
const FORMS = handlers("forms");
const INPUTS = handlers("inputs");
const SWIPES = handlers("swipes");

let currentPath = null;
let currentName = null;
let flashMessage = null;
let flashShown = false;
let flashTimer = null;

const ctx = {
  cloud, data, store, sync, timers,
  go(path) {
    if (location.hash === `#${path}`) render();
    else location.hash = `#${path}`;
  },
  render,
  // A one-line message on the next view, like the desktop's.
  flash(text) {
    flashMessage = text;
    flashShown = false;
    clearTimeout(flashTimer);
    flashTimer = setTimeout(() => {
      flashMessage = null;
      document.querySelector(".flash")?.remove();
    }, FLASH_MS);
  },
};

function route() {
  const path = location.hash.replace(/^#/, "") || "/";
  for (const [pattern, name, view, tab] of ROUTES) {
    const match = path.match(pattern);
    if (match) return { path, name, view, tab, params: match.groups ?? {} };
  }
  return { path: "/", name: "today", view: today.render, tab: "/", params: {} };
}

function crumbHtml(crumbs) {
  const parts = [`<a href="#/" class="home">t1ld3</a>`];
  crumbs.forEach((crumb, index) => {
    const [label, href] = Array.isArray(crumb) ? crumb : [crumb, index === 0 ? TAB_ROOTS[crumb] : null];
    const last = index === crumbs.length - 1;
    parts.push(last || !href ? `<span>${esc(label)}</span>` : `<a href="#${href}">${esc(label)}</a>`);
  });
  return parts.join(`<span class="slash">/</span>`);
}

// The focused add or search box, so a re-render can put focus back.
function focusedField() {
  const element = document.activeElement;
  if (!element || !main.contains(element) || !("value" in element)) return null;
  const owner = element.form?.dataset.form ?? null;
  const key = element.dataset.input ? `[data-input="${element.dataset.input}"]` : owner && element.name
    ? `form[data-form="${owner}"] [name="${element.name}"]` : null;
  return key ? { key, value: element.value, start: element.selectionStart, end: element.selectionEnd } : null;
}

function render() {
  const current = route();
  const signedIn = cloud.signedIn;
  const result = signedIn ? current.view(ctx, current.params) : me.renderSignIn();
  const sameRoute = current.path === currentPath;
  const scroll = sameRoute ? window.scrollY : 0;
  const focus = sameRoute ? focusedField() : null;
  if (!sameRoute) {
    cookbook.onRoute(current, currentName);
    // A flash belongs to the view it was shown on.
    if (flashShown) flashMessage = null;
  }
  currentPath = current.path;
  currentName = current.name;

  document.querySelector(".trail").innerHTML = crumbHtml(result.crumbs);
  document.querySelector("nav").hidden = !signedIn;
  for (const link of document.querySelectorAll("nav a")) {
    link.classList.toggle("on", signedIn && link.getAttribute("href") === `#${current.tab}`);
  }
  main.className = result.className ?? "";
  main.innerHTML = (flashMessage ? `<p class="flash">${esc(flashMessage)}</p>` : "") + result.html;
  flashShown = Boolean(flashMessage);
  window.scrollTo(0, scroll);
  if (focus) {
    const field = main.querySelector(focus.key);
    if (field) {
      field.value = focus.value;
      field.focus({ preventScroll: true });
      try {
        field.setSelectionRange(focus.start, focus.end);
      } catch {
        // Not a text field.
      }
    }
  }
  if (signedIn && current.name === "me") me.mounted();
  renderStatus();
  renderTimers();
}

function renderStatus() {
  const glyphs = { syncing: "~", offline: "!", error: "!" };
  const status = document.querySelector(".status");
  status.textContent = glyphs[sync.status] ?? "";
  status.title = sync.message || sync.status;
}

function renderTimers() {
  const strip = document.querySelector(".timers");
  const lines = timers.lines();
  strip.hidden = !lines.length;
  strip.innerHTML = lines.map((line) => `
    <div class="timer${line.done ? " done" : ""}" data-action="timer-dismiss" data-id="${esc(line.id)}">
      <strong>${esc(line.clock)}</strong><span>${esc(line.label)}</span><span class="x">x</span>
    </div>`).join("");
}

function applyTheme() {
  const theme = data.setting("theme");
  const root = document.documentElement;
  if (theme === "day" || theme === "night") root.dataset.theme = theme;
  else delete root.dataset.theme;
  const night = theme === "night" || (theme !== "day" && matchMedia("(prefers-color-scheme: dark)").matches);
  document.querySelector('meta[name="theme-color"]').content = night ? "#121311" : "#E7E7DD";
}

function fillNoise() {
  const row = () => Array.from({ length: 120 }, () => (Math.random() < 0.18 ? NOISE[1 + Math.floor(Math.random() * (NOISE.length - 1))] : " ")).join("");
  document.querySelector(".noise").textContent = `${row()}\n${row()}`;
}

// Taps, forms, typing and swipes all dispatch by name.

document.addEventListener("click", (event) => {
  const target = event.target.closest("[data-action]");
  if (!target) return;
  const name = target.dataset.action;
  if (name === "go") return ctx.go(target.dataset.to);
  if (name === "timer-dismiss") return timers.dismiss(target.dataset.id);
  ACTIONS[name]?.(ctx, { ...target.dataset }, target);
});

document.addEventListener("submit", (event) => {
  const form = event.target.closest("[data-form]");
  if (!form) return;
  event.preventDefault();
  FORMS[form.dataset.form]?.(ctx, form);
});

document.addEventListener("input", (event) => {
  const name = event.target.dataset?.input;
  if (name) INPUTS[name]?.(ctx, event.target);
});

let touchStart = null;
document.addEventListener("touchstart", (event) => {
  const area = event.target.closest("[data-swipe]") ?? (main.classList.contains("cooking") ? main.querySelector("[data-swipe]") : null);
  touchStart = area ? { name: area.dataset.swipe, x: event.touches[0].clientX, y: event.touches[0].clientY } : null;
}, { passive: true });
document.addEventListener("touchend", (event) => {
  if (!touchStart) return;
  const dx = event.changedTouches[0].clientX - touchStart.x;
  const dy = event.changedTouches[0].clientY - touchStart.y;
  if (Math.abs(dx) > 60 && Math.abs(dy) < 50) SWIPES[touchStart.name]?.(ctx, dx < 0 ? 1 : -1);
  touchStart = null;
}, { passive: true });

// Keep the views current.

window.addEventListener("hashchange", render);
store.listeners.push((kinds) => {
  if (kinds.has("setting")) applyTheme();
  // Synced changes mustn't wipe what someone is typing into an editor.
  if (!EDITORS.has(route().name)) render();
});
sync.listeners.push(() => {
  renderStatus();
  const part = document.querySelector('[data-part="sync"]');
  if (part && route().name === "me") render();
});
let runningTimers = timers.lines().filter((line) => !line.done).length;
timers.listeners.push(() => {
  renderTimers();
  // The cooking view shows "timer running" until it ends.
  const running = timers.lines().filter((line) => !line.done).length;
  if (running !== runningTimers && route().name === "cooking") render();
  runningTimers = running;
});
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", applyTheme);
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") sync.syncNow();
});
setInterval(() => {
  if (document.visibilityState === "visible") sync.syncNow();
}, SYNC_INTERVAL_MS);

if ("serviceWorker" in navigator) navigator.serviceWorker.register("./sw.js").catch(() => {});
fillNoise();
applyTheme();
render();
if (cloud.signedIn) sync.syncNow();

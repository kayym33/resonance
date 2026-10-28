// Small helpers for building the views' HTML.

const ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

// Everything user-typed goes through this before it's put in HTML.
export function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ESCAPES[char]);
}

export function heading(text) {
  return `<h2>${esc(text)}</h2>`;
}

// data-* attributes for a tappable element: action("todo-toggle", {id}).
export function action(name, data = {}) {
  const attributes = Object.entries(data).map(([key, value]) => ` data-${key}="${esc(value)}"`).join("");
  return `data-action="${esc(name)}"${attributes}`;
}

export function button(label, name, data = {}, { solid = false, small = false } = {}) {
  const classes = ["button", solid ? "solid" : "", small ? "small" : ""].filter(Boolean).join(" ");
  return `<button type="button" class="${classes}" ${action(name, data)}>${esc(label)}</button>`;
}

export function picker(label, choices, selected, name) {
  return `<div class="picker"><span class="muted">${esc(label)}</span>${choices
    .map((choice) => `<button type="button" class="chip${choice === selected ? " on" : ""}" ${action(name, { value: choice })}>${esc(choice)}</button>`)
    .join("")}</div>`;
}

// 32 hex characters, like the desktop's uuid4().hex. randomUUID only
// exists on https or localhost, so a copy opened over the local network
// (a phone testing a laptop's server) builds one from random bytes.
export function uuid() {
  if (crypto.randomUUID) return crypto.randomUUID().replaceAll("-", "");
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

// Today as 2026-10-25, in local time.
export function today() {
  const now = new Date();
  const pad = (value) => String(value).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

export function longDate(date = new Date()) {
  return date.toLocaleString("en-GB", { weekday: "long", day: "numeric", month: "long" }).replace(",", "").toLowerCase();
}

export function shorten(text, limit) {
  return text.length <= limit ? text : `${text.slice(0, limit - 1)}…`;
}

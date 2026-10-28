// Account, sync, notifications and theme; and the sign-in screen.
import { disablePush, enablePush, isStandalone, pushStatus } from "../push.js";
import { action, button, esc, heading } from "../ui.js";

const THEMES = ["auto", "day", "night"];
// Filled in after the view renders, since checking is asynchronous.
let notifications = "checking";

function describeSync(sync) {
  if (sync.status === "syncing") return "syncing...";
  if (sync.status === "offline" || sync.status === "error") return `not synced: ${sync.message}`;
  if (sync.status === "synced" && sync.lastSynced) {
    const minutes = Math.floor((Date.now() - sync.lastSynced) / 60000);
    const when = minutes < 1 ? "synced just now" : `synced ${minutes} min ago`;
    return sync.message ? `${when}; ${sync.message}` : when;
  }
  return sync.message || "not synced yet";
}

function notificationPart() {
  if (!isStandalone()) {
    return `<p>To get reminders and timer alerts, add t1ld3 to your home screen first:
      tap <strong>share</strong> in Safari, then <strong>add to home screen</strong>, and open it from there.</p>`;
  }
  switch (notifications) {
    case "on":
      return `<p>on: event reminders and cooking timers come here, and the desktop's <code>phone</code> command.</p>
        <div class="row-buttons">${button("send a test", "me-test")}${button("turn off", "me-push-off")}</div>`;
    case "blocked":
      return `<p>blocked: allow notifications for t1ld3 in the iPhone's Settings, under Notifications.</p>`;
    case "unsupported":
      return `<p>this browser can't receive notifications (iOS 16.4 or later is needed).</p>`;
    case "checking":
      return `<p class="muted">checking...</p>`;
    default:
      return `<p>off.</p><div class="row-buttons">${button("turn on", "me-push-on", {}, { solid: true })}</div>`;
  }
}

export function render(ctx) {
  const theme = ctx.data.setting("theme") ?? "auto";
  return {
    crumbs: ["me"],
    html: `
      ${heading("account")}
      <p>${esc(ctx.cloud.session?.email ?? "")}</p>
      <p class="muted" data-part="sync">${esc(describeSync(ctx.sync))}</p>
      <div class="row-buttons">${button("sync now", "me-sync")}${button("sign out", "me-sign-out")}</div>
      ${heading("notifications")}
      <div data-part="notifications">${notificationPart()}</div>
      <p class="error" data-part="push-error" hidden></p>
      ${heading("theme")}
      <div class="chips">${THEMES.map((choice) => `<button type="button" class="chip${choice === theme ? " on" : ""}" ${action("me-theme", { value: choice })}>${choice}</button>`).join("")}</div>
      <p class="hint">shared with the desktop; auto follows the phone's light and dark mode</p>`,
  };
}

export async function mounted() {
  notifications = await pushStatus();
  const part = document.querySelector('[data-part="notifications"]');
  if (part) part.innerHTML = notificationPart();
}

function showPushError(error) {
  const part = document.querySelector('[data-part="push-error"]');
  if (!part) return;
  part.textContent = error ? error.message ?? String(error) : "";
  part.hidden = !error;
}

export const actions = {
  "me-sync"(ctx) {
    ctx.sync.syncNow();
  },
  async "me-sign-out"(ctx) {
    if (!confirm("sign out on this phone?")) return;
    await disablePush(ctx.cloud).catch(() => {});
    await ctx.cloud.signOut();
    ctx.sync.setStatus("local");
    ctx.go("/");
  },
  "me-theme"(ctx, { value }) {
    ctx.data.saveSetting("theme", value);
  },
  async "me-push-on"(ctx) {
    showPushError(null);
    try {
      await enablePush(ctx.cloud);
    } catch (error) {
      showPushError(error);
    }
    await mounted();
  },
  async "me-push-off"(ctx) {
    showPushError(null);
    await disablePush(ctx.cloud).catch(showPushError);
    await mounted();
  },
  async "me-test"(ctx) {
    showPushError(null);
    try {
      const sent = await ctx.cloud.sendPush("t1ld3", "notifications work ~");
      if (!sent) showPushError(new Error("the server found no phone to send to"));
    } catch (error) {
      showPushError(error);
    }
  },
};

export function renderSignIn() {
  return {
    crumbs: ["sign in"],
    html: `
      <pre class="art center">  .-------.  \n  | t1ld3 |  \n  '-------'  </pre>
      <p class="center muted">sign in with your t1ld3 account</p>
      <form class="editor" data-form="sign-in">
        <label>email<input name="email" type="email" autocomplete="username" required></label>
        <label>password<input name="password" type="password" autocomplete="current-password" required></label>
        <p class="error" hidden></p>
        <button type="submit" class="button solid wide">sign in</button>
      </form>`,
  };
}

export const forms = {
  async "sign-in"(ctx, form) {
    const error = form.querySelector(".error");
    error.hidden = true;
    const submit = form.querySelector("button[type=submit]");
    submit.disabled = true;
    submit.textContent = "signing in...";
    try {
      const session = await ctx.cloud.signIn(form.elements.email.value.trim(), form.elements.password.value);
      ctx.sync.adoptUser(session.user_id);
      await ctx.sync.syncNow();
      ctx.go("/");
    } catch (problem) {
      error.textContent = problem.message;
      error.hidden = false;
      submit.disabled = false;
      submit.textContent = "sign in";
    }
  },
};

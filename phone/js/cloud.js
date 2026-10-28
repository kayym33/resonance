// Minimal Supabase client: email/password auth, the items table, push
// subscriptions and the push function. Mirrors resonance/cloud.py.
import { API_URL, SUPABASE_KEY } from "./config.js";

const SESSION_KEY = "t1ld3.session";
// Refresh this long (seconds) before the access token actually expires.
const REFRESH_MARGIN = 60;
const PAGE_SIZE = 1000;

export class CloudError extends Error {}
export class AuthError extends CloudError {}

function loadSession() {
  try {
    return JSON.parse(localStorage.getItem(SESSION_KEY)) || null;
  } catch {
    return null;
  }
}

function saveSession(session) {
  if (session) localStorage.setItem(SESSION_KEY, JSON.stringify(session));
  else localStorage.removeItem(SESSION_KEY);
}

function sessionFrom(data) {
  return {
    access_token: data.access_token,
    refresh_token: data.refresh_token,
    expires_at: Date.now() / 1000 + Number(data.expires_in ?? 3600),
    user_id: data.user.id,
    email: data.user.email ?? "",
  };
}

function errorMessage(data, fallback) {
  if (data && typeof data === "object") {
    for (const key of ["msg", "message", "error_description", "error"]) {
      if (typeof data[key] === "string") return data[key];
    }
  }
  return fallback;
}

export class Cloud {
  constructor() {
    this.session = loadSession();
    this.refreshing = null;
  }

  get signedIn() {
    return this.session !== null;
  }

  async request(method, path, body, { headers = {}, authorized = true } = {}) {
    const requestHeaders = { apikey: SUPABASE_KEY, "Content-Type": "application/json", ...headers };
    if (authorized) requestHeaders.Authorization = `Bearer ${await this.accessToken()}`;
    let response;
    try {
      response = await fetch(`${API_URL}${path}`, {
        method,
        headers: requestHeaders,
        body: body === undefined ? undefined : JSON.stringify(body),
      });
    } catch {
      throw new CloudError("can't reach the sync server");
    }
    const text = await response.text();
    let data = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = null;
    }
    if (!response.ok) {
      const message = errorMessage(data, `server error ${response.status}`);
      if (response.status === 401 || ([400, 403].includes(response.status) && path.includes("/auth/"))) {
        throw new AuthError(message);
      }
      throw new CloudError(message);
    }
    return data;
  }

  // Auth

  async signIn(email, password) {
    const data = await this.request(
      "POST",
      "/auth/v1/token?grant_type=password",
      { email, password },
      { authorized: false },
    );
    this.session = sessionFrom(data);
    saveSession(this.session);
    return this.session;
  }

  async signOut() {
    const session = this.session;
    this.session = null;
    saveSession(null);
    if (!session) return;
    try {
      await this.request("POST", "/auth/v1/logout", undefined, {
        headers: { Authorization: `Bearer ${session.access_token}` },
        authorized: false,
      });
    } catch {
      // Signed out on this phone either way.
    }
  }

  async accessToken() {
    if (!this.session) throw new AuthError("not signed in");
    if (this.session.expires_at - REFRESH_MARGIN < Date.now() / 1000) {
      // Several requests can notice at once; refresh only once.
      this.refreshing ??= this.refresh().finally(() => {
        this.refreshing = null;
      });
      await this.refreshing;
    }
    return this.session.access_token;
  }

  async refresh() {
    try {
      const data = await this.request(
        "POST",
        "/auth/v1/token?grant_type=refresh_token",
        { refresh_token: this.session.refresh_token },
        { authorized: false },
      );
      this.session = sessionFrom(data);
      saveSession(this.session);
    } catch (error) {
      if (error instanceof AuthError) {
        // The refresh token was revoked or expired.
        this.session = null;
        saveSession(null);
      }
      throw error;
    }
  }

  // Items

  async push(records) {
    if (!records.length || !this.session) return;
    const userId = this.session.user_id;
    await this.request(
      "POST",
      "/rest/v1/items?on_conflict=user_id,kind,id",
      records.map((record) => ({ ...record, user_id: userId })),
      { headers: { Prefer: "resolution=merge-duplicates,return=minimal" } },
    );
  }

  // Rows stored at or after since (server time), oldest first. Pages with
  // offsets on an inclusive cursor, like the desktop: a batch upload gives
  // rows the same timestamp.
  async pull(since) {
    const rows = [];
    for (;;) {
      const query = new URLSearchParams({
        select: "kind,id,data,deleted,updated_at,server_updated_at",
        order: "server_updated_at.asc,kind.asc,id.asc",
        limit: String(PAGE_SIZE),
        offset: String(rows.length),
      });
      if (since) query.set("server_updated_at", `gte.${since}`);
      const page = (await this.request("GET", `/rest/v1/items?${query}`)) ?? [];
      rows.push(...page);
      if (page.length < PAGE_SIZE) return rows;
    }
  }

  // Notifications

  async vapidKey() {
    const data = await this.request("GET", "/functions/v1/push");
    return data?.vapid_public_key ?? null;
  }

  async saveSubscription(subscription, timeZone) {
    const json = subscription.toJSON();
    await this.request(
      "POST",
      "/rest/v1/push_subscriptions?on_conflict=user_id,endpoint",
      [{
        user_id: this.session.user_id,
        endpoint: json.endpoint,
        p256dh: json.keys.p256dh,
        auth: json.keys.auth,
        time_zone: timeZone,
      }],
      { headers: { Prefer: "resolution=merge-duplicates,return=minimal" } },
    );
  }

  async deleteSubscription(endpoint) {
    await this.request("DELETE", `/rest/v1/push_subscriptions?endpoint=eq.${encodeURIComponent(endpoint)}`);
  }

  async sendPush(title, body) {
    const data = await this.request("POST", "/functions/v1/push", { title, body });
    return Number(data?.sent ?? 0);
  }

  // A push the server sends later, even if this app is closed by then.
  async schedulePush(id, sendAt, title, body) {
    await this.request(
      "POST",
      "/rest/v1/scheduled_pushes?on_conflict=user_id,id",
      [{ user_id: this.session.user_id, id, send_at: new Date(sendAt).toISOString(), title, body }],
      { headers: { Prefer: "resolution=merge-duplicates,return=minimal" } },
    );
  }

  async cancelPush(id) {
    await this.request("DELETE", `/rest/v1/scheduled_pushes?id=eq.${encodeURIComponent(id)}`);
  }
}

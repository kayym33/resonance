// Local-first records, like resonance/store.py: every kind keeps
// {id: {data, updated_at, deleted, dirty}}, edits go through put/remove,
// and deletes stay as tombstones so they sync. Saved in localStorage.
// The sync engine (bottom) mirrors resonance/sync.py.
import { AuthError, CloudError } from "./cloud.js";

const RECORDS_KEY = "t1ld3.records";
const SYNC_KEY = "t1ld3.sync";
// The kinds this app shows; the desktop's launcher commands stay there.
export const KINDS = ["task", "event", "recipe", "setting", "profile"];
// Newer than some servers' schema, so pushed on their own (see sync.py).
const NEWER_KINDS = ["recipe"];
const PUSH_BATCH = 500;

function readJson(key, fallback) {
  try {
    return JSON.parse(localStorage.getItem(key)) ?? fallback;
  } catch {
    return fallback;
  }
}

export function nowIso() {
  return new Date().toISOString();
}

// Comparable timestamps. The server keeps microseconds, which Date.parse
// drops, and two edits within a millisecond must still order correctly.
export function isoKey(value) {
  const match = String(value).match(/\.(\d+)/);
  const digits = (match ? match[1] : "").padEnd(6, "0").slice(0, 6);
  const whole = Date.parse(String(value).replace(/\.\d+/, ""));
  return BigInt(whole) * 1000n + BigInt(digits);
}

export class Store {
  constructor() {
    this.records = readJson(RECORDS_KEY, {});
    for (const kind of KINDS) this.records[kind] ??= {};
    // Called after any change, local or synced, with the kinds changed.
    this.listeners = [];
    // Called after local edits only, so the sync engine can upload them.
    this.editListeners = [];
  }

  save() {
    localStorage.setItem(RECORDS_KEY, JSON.stringify(this.records));
  }

  changed(kinds, local) {
    this.save();
    for (const listener of this.listeners) listener(kinds);
    if (local) for (const listener of this.editListeners) listener();
  }

  items(kind) {
    return Object.entries(this.records[kind])
      .filter(([, record]) => !record.deleted)
      .map(([id, record]) => [id, record.data]);
  }

  get(kind, id) {
    const record = this.records[kind][id];
    return record && !record.deleted ? record.data : null;
  }

  put(kind, id, data) {
    this.records[kind][id] = { data: { ...data }, updated_at: nowIso(), deleted: false, dirty: true };
    this.changed(new Set([kind]), true);
  }

  remove(kind, id) {
    if (this.get(kind, id) === null) return;
    this.records[kind][id] = { data: {}, updated_at: nowIso(), deleted: true, dirty: true };
    this.changed(new Set([kind]), true);
  }

  dirtyRecords() {
    const rows = [];
    for (const kind of KINDS) {
      for (const [id, record] of Object.entries(this.records[kind])) {
        if (record.dirty) {
          rows.push({ kind, id, data: record.data, deleted: record.deleted, updated_at: record.updated_at });
        }
      }
    }
    return rows;
  }

  // Clear dirty flags, unless the record changed again meanwhile.
  markPushed(rows) {
    for (const row of rows) {
      const record = this.records[row.kind]?.[row.id];
      if (record && record.updated_at === row.updated_at) record.dirty = false;
    }
    this.save();
  }

  // Merge one row from the server; true if the local copy changed.
  applyRemote(row) {
    if (!KINDS.includes(row.kind)) return false;
    const local = this.records[row.kind][row.id];
    if (local && isoKey(local.updated_at) >= isoKey(row.updated_at)) return false;
    this.records[row.kind][row.id] = {
      data: row.data ?? {},
      updated_at: row.updated_at,
      deleted: Boolean(row.deleted),
      dirty: false,
    };
    return true;
  }

  markAllDirty() {
    for (const kind of KINDS) for (const record of Object.values(this.records[kind])) record.dirty = true;
    this.save();
  }

  clear() {
    for (const kind of KINDS) this.records[kind] = {};
    this.changed(new Set(KINDS), false);
  }
}

// Status is "local" (signed out), "syncing", "synced", "offline" or "error".
export class SyncEngine {
  constructor(store, cloud) {
    this.store = store;
    this.cloud = cloud;
    this.state = readJson(SYNC_KEY, {});
    this.busy = false;
    this.pending = false;
    this.timer = null;
    this.status = cloud.signedIn ? "synced" : "local";
    this.message = "";
    this.lastSynced = null;
    this.listeners = [];
    store.editListeners.push(() => this.requestSync());
  }

  saveState() {
    localStorage.setItem(SYNC_KEY, JSON.stringify(this.state));
  }

  setStatus(status, message = "") {
    this.status = status;
    this.message = message;
    for (const listener of this.listeners) listener();
  }

  // After an edit; a burst of edits syncs once.
  requestSync() {
    if (!this.cloud.signedIn) return;
    clearTimeout(this.timer);
    this.timer = setTimeout(() => this.syncNow(), 1500);
  }

  // The first sign-in keeps what's on this phone; a different account
  // than last time starts fresh, so two people's data never mix.
  adoptUser(userId) {
    if (this.state.user_id === userId) return;
    if (this.state.user_id) this.store.clear();
    else this.store.markAllDirty();
    this.state = { user_id: userId };
    this.saveState();
  }

  async syncNow() {
    clearTimeout(this.timer);
    if (!this.cloud.signedIn) {
      this.setStatus("local");
      return;
    }
    if (this.busy) {
      this.pending = true;
      return;
    }
    this.busy = true;
    this.setStatus("syncing");
    const outgoing = this.store.dirtyRecords();
    try {
      const refused = new Set();
      const established = outgoing.filter((row) => !NEWER_KINDS.includes(row.kind));
      for (let start = 0; start < established.length; start += PUSH_BATCH) {
        await this.cloud.push(established.slice(start, start + PUSH_BATCH));
      }
      for (const kind of NEWER_KINDS) {
        const rows = outgoing.filter((row) => row.kind === kind);
        try {
          for (let start = 0; start < rows.length; start += PUSH_BATCH) {
            await this.cloud.push(rows.slice(start, start + PUSH_BATCH));
          }
        } catch (error) {
          if (error instanceof AuthError || !String(error.message).includes("items_kind_check")) throw error;
          refused.add(kind);
        }
      }
      const rows = await this.cloud.pull(this.state.cursor);
      this.store.markPushed(outgoing.filter((row) => !refused.has(row.kind)));
      const changed = new Set();
      for (const row of rows) if (this.store.applyRemote(row)) changed.add(row.kind);
      if (rows.length) {
        const newest = rows.reduce((a, b) => (isoKey(b.server_updated_at) > isoKey(a.server_updated_at) ? b : a));
        this.state.cursor = newest.server_updated_at;
        this.saveState();
      }
      if (changed.size) this.store.changed(changed, false);
      this.lastSynced = Date.now();
      this.setStatus("synced", refused.size ? "recipes wait for the server" : "");
    } catch (error) {
      if (error instanceof AuthError) {
        this.setStatus(this.cloud.signedIn ? "error" : "local", error.message);
      } else {
        this.setStatus("offline", error instanceof CloudError ? error.message : String(error));
      }
    } finally {
      this.busy = false;
    }
    if (this.pending) {
      this.pending = false;
      this.syncNow();
    }
  }
}

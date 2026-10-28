// Called every minute by pg_cron (supabase/cron.sql). Sends event
// reminders and cooking timers that are due to users' phones.
//
// Deployed with --no-verify-jwt: cron sends a shared secret (CRON_SECRET)
// instead of a user's token. It reads every user's events, so it uses the
// service role key, which edge functions get from Supabase itself; it
// never leaves the server.
import { createClient } from "npm:@supabase/supabase-js@2.45.4";
import { dueReminders, localNow, nearbyDays, reminderText } from "../_shared/reminders.js";
import { json, sendToAll, type Subscription } from "../_shared/webpush.ts";

// Sent-reminder records older than this are cleared out.
const KEEP_SENT_DAYS = 3;

interface PhoneRow extends Subscription {
  user_id: string;
  time_zone: string;
}

function validZone(zone: string): string {
  try {
    new Intl.DateTimeFormat("en", { timeZone: zone });
    return zone;
  } catch {
    return "UTC";
  }
}

Deno.serve(async (request) => {
  const secret = Deno.env.get("CRON_SECRET");
  if (!secret || request.headers.get("x-cron-secret") !== secret) return json({ error: "not allowed" }, 401);
  const admin = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!, {
    auth: { persistSession: false },
  });
  const now = new Date();
  let timers = 0;
  let reminders = 0;

  const { data: phones, error } = await admin
    .from("push_subscriptions")
    .select("user_id, endpoint, p256dh, auth, time_zone");
  if (error) return json({ error: error.message }, 500);
  const byUser = new Map<string, PhoneRow[]>();
  for (const phone of (phones ?? []) as PhoneRow[]) {
    byUser.set(phone.user_id, [...(byUser.get(phone.user_id) ?? []), phone]);
  }

  // Cooking timers started on a phone.
  const { data: dueTimers } = await admin
    .from("scheduled_pushes")
    .select("user_id, id, title, body")
    .lte("send_at", now.toISOString());
  for (const timer of dueTimers ?? []) {
    // Delete first: if two runs overlap, only one gets to send it.
    const { data: claimed } = await admin
      .from("scheduled_pushes")
      .delete()
      .eq("user_id", timer.user_id)
      .eq("id", timer.id)
      .select("id");
    if (!claimed?.length) continue;
    timers += await sendToAll(admin, byUser.get(timer.user_id) ?? [], {
      title: timer.title, body: timer.body, tag: `timer-${timer.id}`, url: "./#/cook",
    });
  }

  // Event reminders, worked out in each phone's own time zone.
  for (const [userId, userPhones] of byUser) {
    const zones = new Map<string, PhoneRow[]>();
    for (const phone of userPhones) {
      const zone = validZone(phone.time_zone);
      zones.set(zone, [...(zones.get(zone) ?? []), phone]);
    }
    for (const [zone, zonePhones] of zones) {
      const nowLocal = localNow(now, zone);
      const { data: rows } = await admin
        .from("items")
        .select("id, data")
        .eq("user_id", userId)
        .eq("kind", "event")
        .eq("deleted", false)
        .in("data->>day", nearbyDays(nowLocal));
      for (const due of dueReminders(rows ?? [], nowLocal)) {
        // Recording it first means it goes out once, even if runs overlap.
        const { data: recorded } = await admin
          .from("sent_reminders")
          .upsert({ user_id: userId, key: `${zone}|${due.key}` }, { onConflict: "user_id,key", ignoreDuplicates: true })
          .select("key");
        if (!recorded?.length) continue;
        const { title, body } = reminderText(due.data, nowLocal);
        reminders += await sendToAll(admin, zonePhones, { title, body, tag: `event-${due.id}`, url: "./#/cal" });
      }
    }
  }

  await admin
    .from("sent_reminders")
    .delete()
    .lt("sent_at", new Date(now.getTime() - KEEP_SENT_DAYS * 86400000).toISOString());
  return json({ timers, reminders });
});

// Sends web pushes to a user's phones, and forgets phones that are gone.
import webpush from "npm:web-push@3.6.7";
import type { SupabaseClient } from "npm:@supabase/supabase-js@2.45.4";

export interface Subscription {
  endpoint: string;
  p256dh: string;
  auth: string;
}

let configured = false;

function configure(): void {
  if (configured) return;
  const publicKey = Deno.env.get("VAPID_PUBLIC_KEY");
  const privateKey = Deno.env.get("VAPID_PRIVATE_KEY");
  if (!publicKey || !privateKey) throw new Error("VAPID keys aren't set (see phone/README.md)");
  webpush.setVapidDetails(Deno.env.get("VAPID_SUBJECT") ?? "mailto:t1ld3@example.com", publicKey, privateKey);
  configured = true;
}

// Returns how many phones took the message. Subscriptions the push
// service says are gone (the app was removed, or notifications turned
// off) are deleted, through ``client`` (scoped to the user, or admin).
export async function sendToAll(
  client: SupabaseClient,
  subscriptions: Subscription[],
  message: { title: string; body: string; tag?: string; url?: string },
): Promise<number> {
  configure();
  const payload = JSON.stringify(message);
  let sent = 0;
  await Promise.all(subscriptions.map(async (subscription) => {
    try {
      await webpush.sendNotification(
        { endpoint: subscription.endpoint, keys: { p256dh: subscription.p256dh, auth: subscription.auth } },
        payload,
        { TTL: 60 * 60 },
      );
      sent += 1;
    } catch (error) {
      const status = (error as { statusCode?: number }).statusCode;
      if (status === 404 || status === 410) {
        await client.from("push_subscriptions").delete().eq("endpoint", subscription.endpoint);
      } else {
        console.error("push failed", status, (error as Error).message);
      }
    }
  }));
  return sent;
}

export const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, apikey, content-type, x-client-info",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
};

export function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
  });
}

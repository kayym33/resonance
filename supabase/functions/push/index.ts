// POST {title, body}: push a notification to the signed-in user's phones.
// Used by the desktop (finished cooking timers, the "phone" command) and
// the phone's "send a test". GET returns the VAPID public key the phone
// subscribes with.
//
// Deployed with --no-verify-jwt so browsers' CORS preflights get through;
// the user's token is checked here instead. Every query runs as that
// user, so row-level security limits it to their own phones.
import { createClient } from "npm:@supabase/supabase-js@2.45.4";
import { CORS_HEADERS, json, sendToAll } from "../_shared/webpush.ts";

const MAX_TITLE = 120;
const MAX_BODY = 500;

Deno.serve(async (request) => {
  if (request.method === "OPTIONS") return new Response("ok", { headers: CORS_HEADERS });
  const token = request.headers.get("Authorization")?.replace(/^Bearer\s+/i, "");
  if (!token) return json({ error: "sign in first" }, 401);

  const client = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_ANON_KEY")!, {
    global: { headers: { Authorization: `Bearer ${token}` } },
    auth: { persistSession: false },
  });
  const { data: { user }, error } = await client.auth.getUser(token);
  if (error || !user) return json({ error: "sign in again" }, 401);

  if (request.method === "GET") {
    return json({ vapid_public_key: Deno.env.get("VAPID_PUBLIC_KEY") ?? null });
  }
  if (request.method !== "POST") return json({ error: "use POST" }, 405);

  let message: { title?: unknown; body?: unknown };
  try {
    message = await request.json();
  } catch {
    return json({ error: "send JSON: {title, body}" }, 400);
  }
  const title = typeof message.title === "string" ? message.title.slice(0, MAX_TITLE) : "";
  const body = typeof message.body === "string" ? message.body.slice(0, MAX_BODY) : "";
  if (!title && !body) return json({ error: "nothing to send" }, 400);

  const { data: subscriptions, error: queryError } = await client
    .from("push_subscriptions")
    .select("endpoint, p256dh, auth");
  if (queryError) return json({ error: queryError.message }, 500);
  try {
    const sent = await sendToAll(client, subscriptions ?? [], { title: title || "t1ld3", body });
    return json({ sent });
  } catch (sendError) {
    return json({ error: (sendError as Error).message }, 500);
  }
});

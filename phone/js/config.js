// The same Supabase project as the desktop app (resonance/constants.py).
// The publishable key is public by design: row-level security limits
// every signed-in user to their own rows. Never put the service_role key
// here.
export const SUPABASE_URL = "https://zuzpyrwoovdavbuqrqpx.supabase.co";
export const SUPABASE_KEY = "sb_publishable_OXVfSivrBGVRZL1wr4J9Fw_xUql8kyQ";

// Tests point a locally served copy at a stand-in server with ?api=<url>.
// Only on localhost: on the real site, a link with ?api= could otherwise
// send someone's password to another server.
function apiUrl() {
  const local = (host) => host === "localhost" || host === "127.0.0.1";
  const override = new URLSearchParams(location.search).get("api");
  if (override && local(location.hostname)) {
    try {
      if (local(new URL(override).hostname)) return override;
    } catch {
      // Not a URL; use the real server.
    }
  }
  return SUPABASE_URL;
}

export const API_URL = apiUrl().replace(/\/$/, "");

# t1ld3 on your phone

A home-screen web app for iPhone (it works on Android too): to-dos, the
calendar and the cookbook, synced with the desktop through the same
Supabase account. Notifications (event reminders, cooking timers and the
desktop's `phone <note>` command) are pushed from two small Supabase edge
functions, because iOS doesn't let a home-screen app schedule its own.

It's plain HTML, CSS and JavaScript modules, with no build step.
GitHub Pages serves this folder as it is.

## Setting it up (once)

You need the Supabase dashboard, a terminal in this repo (with Node, for
`npx`) and the GitHub repo's settings.

1. **Database.** In Supabase, open the SQL editor, paste all of
   `supabase/schema.sql` and run it. It's safe to run again. Running it also
   lets recipes sync on the desktop.

2. **Keys.** Make the keys that sign push messages, and a secret for the
   once-a-minute job:

   ```bash
   npx web-push generate-vapid-keys
   openssl rand -hex 24
   ```

3. **Edge functions.** Sign the Supabase CLI in, link the project, store the
   secrets and deploy both functions:

   ```bash
   npx supabase login
   npx supabase link --project-ref zuzpyrwoovdavbuqrqpx
   npx supabase secrets set \
     VAPID_PUBLIC_KEY=<public key> \
     VAPID_PRIVATE_KEY=<private key> \
     VAPID_SUBJECT=mailto:<your email> \
     CRON_SECRET=<the random secret>
   npx supabase functions deploy push --no-verify-jwt
   npx supabase functions deploy reminders --no-verify-jwt
   ```

   `--no-verify-jwt` is deliberate. `push` checks the user's token itself,
   so browsers' CORS preflights get through, and `reminders` only answers
   requests that carry `CRON_SECRET`.

4. **The minute job.** In the SQL editor, store the same secret in the
   vault (once), then run `supabase/cron.sql`:

   ```sql
   select vault.create_secret('<the random secret>', 't1ld3_cron_secret');
   ```

5. **Hosting.** GitHub Pages serves the app at <https://t1ld3.kaylamc.uk/>
   (Settings → Pages: Source **GitHub Actions**, custom domain
   `t1ld3.kaylamc.uk`, Enforce HTTPS). The DNS for kaylamc.uk is at LCN,
   where `t1ld3` is a CNAME to `kayym33.github.io`. Every push to `main`
   that touches `phone/` deploys it (`.github/workflows/phone.yml`), or
   run the workflow by hand from the Actions tab. Keep the address: the
   phone keeps its sign-in, data and notification permission per address,
   so moving it means adding it to the home screen again.

## On the iPhone

1. Open the link in **Safari**, sign in with your t1ld3 account.
2. Tap **share**, then **add to home screen**, and open t1ld3 from the
   new icon.
3. In **me**, tap **turn on** under notifications and allow them. Then
   **send a test**.

Notifications need iOS 16.4 or later, and only work in the home-screen
app, not in a Safari tab.

## How it fits together

- `js/store.js` keeps every record locally (localStorage) and syncs the
  same way the desktop does (`resonance/store.py`, `resonance/sync.py`):
  last write wins, deletes are tombstones, and recipes are uploaded on
  their own, so a server without the latest schema only holds them back.
- `js/recipes.js` is a port of `resonance/recipes.py`. `tests/parity.mjs`
  runs the same inputs through both and fails if they differ. Run it after
  changing either file.
- Cooking timers count down on screen and also add a row to
  `scheduled_pushes`, so the notification arrives even if the app is
  closed. `supabase/functions/reminders` sends those and event
  reminders every minute, in each phone's own time zone
  (`tests/reminders.mjs` tests the timing).
- `js/gestures.js` makes it feel like an iPhone app: swipe back from
  the left edge (only from the home screen; in Safari, Safari's own swipe
  does it), swipe a to-do right to tick it or left to delete it, swipe
  between cooking steps, and pull down to sync. Pages slide in and out
  like iOS ones, each page remembers its scroll position, and tapping the
  tab you're on goes back to its first page. `splash/` holds a launch
  screen for each iPhone size; a new iPhone size needs its own image, or
  it opens on a blank screen.
- `?api=<url>` points a copy served from `localhost` at a stand-in
  server, for testing. It's ignored anywhere else, so a link can't send
  your password to another server.

## Tests

```bash
node phone/tests/parity.mjs     # phone and desktop recipe code agree
node phone/tests/reminders.mjs  # when reminders are due, across time zones
```

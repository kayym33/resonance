# Adding a new t1ld3 user

Accounts are invite-only: you create each one by hand. Every account only
ever sees its own data (row-level security in Supabase), so there's
nothing to separate between people.

## Once, before your first friend

- [ ] **Sign-ups are off.** Supabase → Authentication → Sign In / Providers →
  "Allow new users to sign up" is **off**. Otherwise anyone with the app
  can make an account.
- [ ] **There's a release to give them.** New features (app menu, cookbook,
  phone app) are only in the `t1ld3.exe` / `t1ld3-linux` downloads once
  they're merged into `main`.
- [ ] **The phone app is set up** (only needed for the phone): follow
  `phone/README.md`.

## You, for each new person

1. **Create their t1ld3 account.** Supabase → Authentication → Users →
   **Add user → Create new user**. Enter their email and a temporary
   password, and tick **Auto Confirm User** so no confirmation email is
   needed.
2. **Let them use Spotify.** Spotify Developer Dashboard → the t1ld3 app →
   **Settings → User Management** → add their name and the email of
   **their Spotify account** (it can differ from the one in step 1).
   Development mode only allows a small number of users, and only listed
   ones can sign in. Playback controls need Spotify Premium.
3. **Send them:**
   - the download link: <https://github.com/kayym33/resonance/releases/latest>
   - their email and temporary password
   - the phone app address: <https://t1ld3.kaylamc.uk/>
   - the "For them" section below

## For them

### On the computer

1. **Download and open the app.**
   - **Windows:** download `t1ld3.exe` and open it. It isn't code-signed,
     so Windows shows "Windows protected your PC": click
     **More info → Run anyway**. After that it updates itself.
   - **Linux:** download `t1ld3-linux`, then run
     `chmod +x t1ld3-linux && ./t1ld3-linux`.
2. **Sign in** when the app asks, with the email and temporary password.
   Then change the password: click your name at the top right of the hub
   to open your account.
3. **Connect Spotify.** The first time, your browser opens Spotify's
   sign-in page. Approve it once on each computer.
4. **Weather:** choose whether to share your location, or type in a city.

### On an iPhone

1. Open <https://t1ld3.kaylamc.uk/> in **Safari** and sign in
   with the same account.
2. Tap **Share → Add to Home Screen**, then open t1ld3 from the new icon.
3. Go to **me**, tap **turn on** under notifications and allow them, then
   tap **send a test**.

Notifications need iOS 16.4 or later, and only work from the home-screen
icon, not in a Safari tab.

## If something goes wrong

| Problem | Fix |
| --- | --- |
| Spotify says the user isn't registered | They're missing from User Management, or the email there isn't the one on their Spotify account. |
| "Invalid login credentials" | Check the account exists in Supabase and is confirmed, and that the password was typed exactly. |
| Signing in on a computer someone else used | The app asks first, then clears the previous person's data on that computer before syncing the new account. |
| No notifications on the iPhone | Make sure they opened t1ld3 from the home-screen icon, and that notifications are allowed for t1ld3 in Settings → Notifications. |

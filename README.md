# t1ld3

t1ld3 (formerly Resonance) is a small desktop hub for Windows and Linux,
drawn in a monochrome, ASCII-art terminal style. One window holds a command
launcher, what's playing on Spotify, the weather, a to-do list and a
calendar. The Spotify player can pop out into its own always-on-top window
that stays open when you close the hub.

## What you can do

- **Launcher.** Type a command at the `>` prompt to open apps and folders,
  search the web, play a song, add a to-do or do quick sums.
- **Now playing.** See the current track as dithered ASCII album art, and
  skip, play or pause.
- **Player.** Pop out a compact, always-on-top player with seek and volume
  controls.
- **Weather.** Current conditions for your city.
- **To-do list.** Add, tick off and clear tasks.
- **Calendar.** Today, 3-day, week and month views. Double-click to add an
  event.

## Requirements

- Windows or Linux
- A Spotify account, added to t1ld3's Spotify app by its owner (see below)
- Spotify Premium for playback controls
- An internet connection

## Start t1ld3

### Windows executable

Download `t1ld3.exe` from the latest
[GitHub Release](https://github.com/kayym33/resonance/releases/latest) and
double-click it. If Windows shows a security warning, check that the file came
from that page before choosing **Run**.

### Python version (Windows or Linux)

Install Python 3.10 or newer. On Ubuntu or Debian, also install Tkinter and
virtual-environment support:

```bash
sudo apt install python3 python3-pip python3-venv python3-tk
```

Then, from the project folder:

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m pip install spotipy customtkinter pillow
python main.py
```

## Sign in to Spotify

The first time t1ld3 starts, your browser opens Spotify's sign-in page.
Approve access and return to t1ld3. You only do this once per computer.

t1ld3 uses one shared Spotify app, and while that app is in Spotify's
Development mode, only people its owner has added can sign in. If the browser
says you aren't allowed, ask the owner to add you.

**Owner:** in the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard),
open the app, go to **User Management**, and add the person's name and the
email address of their Spotify account. Spotify allows up to 25 people. The
app's redirect URIs must include `http://127.0.0.1:8888/callback` exactly
(`localhost` doesn't count as the same address).

## Accounts and sync

Sign in to keep your to-dos, calendar, weather location, launcher commands
and display name the same on every computer. t1ld3 offers to sign you in the
first time it starts. Later, click the name (or **sign in**) at the top right
of the hub, right-click and choose **Account**, or type `account` in the
launcher.

Accounts are invite-only. **Owner:** create them in the Supabase dashboard
under **Authentication → Users → Add user**, and keep **Allow new users to
sign up** turned off. People can change their password from the account
window.

You can also use t1ld3 without an account. Everything works the same and
stays on that computer, and it uploads the first time you sign in. Edits made
offline sync when you're back online. If the same thing was changed on two
computers, the most recent change wins. Launcher commands sync separately for
Windows and Linux, and window size and Spotify sign-in stay per computer.

**Owner, one-time setup:** run `supabase/schema.sql` in the Supabase SQL
editor. It creates the table that holds everyone's data, with rules so each
person can only reach their own.

## Using the hub

### Launcher

Start typing in the `>` prompt. Use **Up**/**Down** to pick a suggestion,
**Enter** to run it, **Tab** to fill it in and **Esc** to clear.

| Type | What happens |
| --- | --- |
| `zen`, `term` | Open Zen browser or a terminal |
| `p <project>` | Open a project from `~/Projects` in a terminal and VS Code |
| `files <folder>` | Open a folder in the file manager |
| `g <search>`, `yt <search>` | Search the web or YouTube |
| `play <song>` | Play the top Spotify result |
| `todo <task>` | Add a to-do |
| `= 12*7` | Calculate; **Enter** copies the answer |
| `cal`, `home` | Switch hub pages |
| `player`, `quit` | Pop out the player, or quit |

Anything else becomes a web search. The commands live in `commands.json` in
the data folder (see below), and you can add your own. `{args}` is replaced
by whatever you type after the command name. Changes take effect the next
time you click into the prompt.

### Keyboard shortcut

Starting t1ld3 while it's already running brings the hub to the front, so you
can put the launcher on a key. In GNOME, open **Settings → Keyboard → Custom
Shortcuts** and add a shortcut that runs:

```bash
/path/to/project/.venv/bin/python /path/to/project/main.py
```

### Weather

On first run, the weather panel asks whether to share your location. Sharing
looks up your nearest city from your IP address (through ipinfo.io) each
time t1ld3 starts. Otherwise, type a city. Use **change** to switch later.
Forecasts come from [Open-Meteo](https://open-meteo.com).

### Calendar

Switch to the **calendar** tab. Double-click an empty slot to add an event,
or a day in month view. Leave the start time empty for an all-day event.
Click an event to edit or delete it.

### Menu and player

Right-click anywhere in the hub or the player for more options:

- pop out the player, or open the hub
- open Spotify and refresh the current song
- change the size
- check for updates, and About
- close the window, or quit

Closing the hub leaves the player running. t1ld3 quits once both windows are
closed. **Ctrl+Q** quits from either window.

## Your data

Everything is stored on your computer in the data folder:

| System | Folder |
| --- | --- |
| Windows | `%LOCALAPPDATA%\t1ld3` |
| Linux | `~/t1ld3` |

The folder holds `todo.json`, `events.json`, `commands.json`,
`settings.json`, `profile.json` and `device.json`, plus the sync bookkeeping
in `sync.json`. It also holds two sign-in files that you shouldn't share:
`spotify-token.json` for Spotify and `session.json` for your t1ld3 account. A `Resonance` folder from an older version is moved here
automatically.

## Updates (Windows)

When a pull request is merged into `main`, GitHub Actions bumps the patch
version, builds `t1ld3.exe` and publishes a GitHub Release. Right-click and
choose **Check for updates**. After you confirm, t1ld3 downloads the new
version, closes, replaces itself and restarts. Releases also include a copy named
`Resonance.exe`, so that copies installed before the rename can update too.

## Troubleshooting

### The browser says I can't sign in to Spotify

Your Spotify account needs to be added to the app by its owner. See
[Sign in to Spotify](#sign-in-to-spotify).

### Playback controls don't work

Playback controls need Spotify Premium and an active device. Open Spotify,
play something on a device, then try again.

### Sign in with a different Spotify account

Quit t1ld3, delete `spotify-token.json` from the data folder, then start
t1ld3 again.

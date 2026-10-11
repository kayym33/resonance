# Resonance

Resonance is a small Windows desktop music companion that displays the currently
playing Spotify track, album artwork, playback progress, and playback controls.

## Features

- Fixed `300x400` music player window
- Current song, artist, and album artwork
- Track progress and duration
- Rotating italic quotes beneath the time
- Previous, play/pause, and next controls
- Right-click menu:
  - Open the Spotify desktop app
  - Enable or disable always-on-top
  - Refresh the current song
  - Exit the app
- Custom app icon

You can edit or add quotes in `assets\quotes.json`. Quotes rotate every
30 seconds while the app is running.

## Project structure

```text
clock/
├── main.py                 # Application entry point
├── resonance/              # Python package
│   ├── backend.py          # Spotify API integration
│   ├── frontend.py         # CustomTkinter user interface
│   ├── setup.py            # First-run credential setup
│   └── __init__.py
├── assets/
│   ├── icon.ico            # Application icon
│   ├── icon-original.jpg   # Original artwork
│   ├── pink_theme.json     # CustomTkinter theme
│   └── quotes.json         # Rotating quotes
└── README.md
```

## Requirements

- Windows
- Python 3.10 or newer
- A Spotify account
- Spotify Premium for playback controls
- Spotify open on an active device

## Spotify setup

1. Open the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard).
2. Create an app and select **Web API**.
3. In the app settings, add this exact redirect URI:

   ```text
   http://127.0.0.1:8888/callback
   ```

   `localhost` is not accepted by Spotify's current redirect URI rules.
4. Copy the app's **Client ID** and **Client Secret**.

## Run from source

Open PowerShell in the project folder and install the dependencies:

```powershell
py -m pip install spotipy customtkinter pillow
```

Set the Spotify credentials in the same PowerShell window:

```powershell
$env:SPOTIPY_CLIENT_ID = "your-client-id"
$env:SPOTIPY_CLIENT_SECRET = "your-client-secret"
$env:SPOTIPY_REDIRECT_URI = "http://127.0.0.1:8888/callback"
```

Start Resonance:

```powershell
py main.py
```

The first run shows a setup window for the Spotify credentials, then opens
Spotify authorization in a browser. Approve the requested permissions and
return to the app. Credentials are saved locally in
`%LOCALAPPDATA%\Resonance\spotify.json`; they are not included in the
executable. Delete that file to show the setup window again.

## Controls

| Action | Control |
| --- | --- |
| Previous track | `⏮` |
| Play or pause | `▶` / `⏸` |
| Next track | `⏭` |
| Context menu | Right-click |
| Close | Native close button, context menu **Exit**, `Ctrl+Q`, or `Escape` |

## Build a Windows executable

Install PyInstaller:

```powershell
py -m pip install pyinstaller
```

Build the executable:

```powershell
pyinstaller --onefile --windowed --name Resonance `
  --icon=assets\icon.ico `
  --add-data "assets\pink_theme.json;assets" `
  --add-data "assets\icon.ico;assets" `
  --add-data "assets\quotes.json;assets" `
  main.py
```

The executable is created at:

```text
dist\Resonance.exe
```

Send the executable and this README to another user. They must use their own
Spotify credentials and authorize the app with their own Spotify account.

If the Spotify app is in Development mode, add their Spotify account as a test
user in the Spotify Developer Dashboard first.

## Security

- Never commit or share `SPOTIPY_CLIENT_SECRET`.
- Never share the `.cache` file. It contains an authorization token.
- Each user should authorize the app with their own Spotify account.

## Troubleshooting

### No client ID

Set the three `SPOTIPY_*` environment variables in the same PowerShell window
used to start the app.

### Authorization or permission errors

Delete the local token cache and authorize again:

```powershell
Remove-Item .cache
py main.py
```

Only run this command from the Resonance folder, and only if `.cache` exists.

### Playback controls do not work

Playback controls require Spotify Premium and an active Spotify device. Open
Spotify on the desktop or phone, select a device, and try again.

### Album artwork does not load

Check that the computer is connected to the internet. Artwork is downloaded
from Spotify when the track changes.

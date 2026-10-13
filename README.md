# t1ld3

t1ld3 is a small Windows desktop companion for Spotify. It shows the
currently playing track in a compact window and gives you quick playback
controls without opening the full Spotify window.

## What you can do

- See the current song, artist, album artwork, progress, and duration.
- Play or pause the current track.
- Skip to the previous or next track.
- Adjust the Spotify device volume with the volume slider.
- Seek within the current track with the playback slider.
- Keep the player window on top of other windows.
- Open Spotify, refresh the current track, or exit from the right-click menu.
- Display rotating quotes beneath the playback time.

## Requirements

- Windows or Linux
- A Spotify account
- Spotify installed and signed in on at least one device
- Spotify Premium for playback controls
- An internet connection

## First-time setup

Before opening t1ld3, create a Spotify developer application:

1. Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
   and sign in.
2. Create an application and choose **Web API** if Spotify asks which
   product you want to use.
3. Open the application's settings and add this redirect URI exactly:

   ```text
   http://127.0.0.1:8888/callback
   ```

   Do not replace `127.0.0.1` with `localhost`.
4. Copy the application's **Client ID** and **Client Secret**. Keep the
   secret private.

## Start t1ld3

### Using the Windows executable

The included `t1ld3.exe` is for Windows. Double-click it to start the
application. If Windows displays a security warning, verify that the file came
from the person or location you trust before choosing **Run**.

### Using the Python version on Windows

If you received the source-code version instead of the executable, install
Python 3.10 or newer, open PowerShell in the t1ld3 folder, and run:

```powershell
py -m pip install spotipy customtkinter pillow
py main.py
```

### Using the Python version on Linux

Install Python, Tkinter, and virtual-environment support. On Ubuntu or Debian,
run:

```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv python3-tk
```

Then, from the t1ld3 folder, create an environment and start the app:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install spotipy customtkinter pillow
python main.py
```

The Windows `.exe` is not required on Linux; run the Python version instead.

## Update the Windows app

Windows executable updates are published through GitHub Releases. When a pull
request is merged into `main`, GitHub Actions automatically:

1. Increments the patch version, such as `0.1.1` to `0.1.2`.
2. Commits the new `APP_VERSION` back to `main`.
3. Builds `t1ld3.exe` on a Windows runner.
4. Creates a matching GitHub Release, such as `v0.1.2`.

Users can then right-click the Windows app and choose **Check for updates**.
After they confirm, t1ld3 downloads the new executable, closes, replaces
it, and starts the updated version. Updates are downloaded only after the user
confirms the prompt.

## Connect your Spotify account

The first time t1ld3 starts, it asks for:

- **Spotify Client ID** — from your Spotify developer application.
- **Spotify Client Secret** — from the same application.
- **Redirect URI** — leave this as:

  ```text
  http://127.0.0.1:8888/callback
  ```

Choose **Save and continue**, then approve access in the browser window that
opens. Return to t1ld3 after authorization.

If your Spotify application is in Development mode, the Spotify account you
use must be added as a test user in the application's dashboard.

## Controls

| Action | How to use it |
| --- | --- |
| Previous track | Select `⏮` |
| Play or pause | Select `▶` or `⏸` |
| Next track | Select `⏭` |
| Playback position | Drag the progress slider |
| Volume | Drag the volume slider |
| More options | Right-click anywhere in the window |
| About t1ld3 | Right-click, then select **About t1ld3** |
| Change size | Right-click, then choose **Size** and select **Small**, **Medium**, or **Large** |
| Close t1ld3 | Use the window close button, **Exit**, `Ctrl+Q`, or `Escape` |

Playback controls work only when Spotify Premium is active and Spotify has an
available playback device. Open Spotify, select a device, and try again if
the controls do not respond.

In **Small** mode, move the pointer over the bottom 20% of the window to
reveal the playback buttons.

## Your credentials and privacy

t1ld3 stores the Spotify application details locally on your computer at:

```text
%LOCALAPPDATA%\t1ld3\spotify.json
```

The application uses Spotify authorization to access your playback
information. It does not include your credentials in the executable.

Never share your Spotify Client Secret or authorization cache. If you are
using a copy of t1ld3 from someone else, create and use your own Spotify
developer application.

## Troubleshooting

### The setup window keeps appearing

Check that the Client ID and Client Secret are correct, then save them again.
If you are using the Python version, make sure the three `SPOTIPY_*`
environment variables are set in the same PowerShell window used to start the
app.

### Authorization fails

Confirm that the redirect URI in the Spotify Developer Dashboard matches this
value exactly:

```text
http://127.0.0.1:8888/callback
```

Also confirm that your Spotify account is listed as a test user when the
developer application is in Development mode.

### Playback controls do not work

Playback controls require Spotify Premium and an active Spotify device. Open
Spotify, select a device, and then try the control again.

### Album artwork does not load

Check your internet connection. Artwork is downloaded from Spotify when the
track changes.

### Start over with a different Spotify account

Close t1ld3 and delete this file:

```text
%LOCALAPPDATA%\t1ld3\spotify.json
```

Start t1ld3 again and enter the credentials for the Spotify developer
application you want to use.

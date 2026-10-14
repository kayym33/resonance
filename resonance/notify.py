"""Desktop notifications with no extra dependencies.

``send`` blocks for a moment, so call it from ``app.worker``. It returns
False when the system couldn't show anything, so the caller can fall back
to the in-app toast.
"""

from __future__ import annotations

import os
import subprocess

from .constants import APP_NAME
from .windows import ICON_PATH

NOTIFY_TIMEOUT_S = 10
CREATE_NO_WINDOW = 0x08000000
# Windows only shows toasts from registered apps; PowerShell is always one.
POWERSHELL_APP_ID = (
    "{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\\WindowsPowerShell\\v1.0\\powershell.exe"
)
# The text arrives through environment variables, never inside the script.
WINDOWS_TOAST_SCRIPT = f"""
$ErrorActionPreference = 'Stop'
$null = [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]
$xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$text = $xml.GetElementsByTagName('text')
$null = $text.Item(0).AppendChild($xml.CreateTextNode($env:T1LD3_TITLE))
$null = $text.Item(1).AppendChild($xml.CreateTextNode($env:T1LD3_BODY))
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('{POWERSHELL_APP_ID}').Show($toast)
"""


def send(title: str, body: str) -> bool:
    try:
        if os.name == "nt":
            result = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", WINDOWS_TOAST_SCRIPT],
                env={**os.environ, "T1LD3_TITLE": title, "T1LD3_BODY": body},
                capture_output=True,
                timeout=NOTIFY_TIMEOUT_S,
                creationflags=CREATE_NO_WINDOW,
            )
        else:
            result = subprocess.run(
                [
                    "notify-send",
                    f"--app-name={APP_NAME}",
                    f"--icon={ICON_PATH}",
                    "--",
                    title,
                    body,
                ],
                capture_output=True,
                timeout=NOTIFY_TIMEOUT_S,
            )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0

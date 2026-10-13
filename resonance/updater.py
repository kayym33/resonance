from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from .constants import APP_NAME, GITHUB_RELEASES_API

# Releases from before the rename only have Resonance.exe.
ASSET_NAMES = (f"{APP_NAME}.exe", "Resonance.exe")


def parse_version(version: str) -> tuple[int, ...]:
    numbers = re.findall(r"\d+", version.lstrip("v"))
    return tuple(int(number) for number in numbers) or (0,)


def find_update() -> tuple[str, str] | None:
    request = Request(
        GITHUB_RELEASES_API,
        headers={"Accept": "application/vnd.github+json"},
    )
    with urlopen(request, timeout=10) as response:
        release: Any = json.load(response)

    if not isinstance(release, dict):
        raise ValueError("GitHub returned an invalid release response")

    tag_name = release.get("tag_name")
    assets = release.get("assets")
    if not isinstance(tag_name, str) or not isinstance(assets, list):
        raise ValueError("GitHub release is missing version or assets")

    download_urls = {
        asset.get("name"): asset.get("browser_download_url")
        for asset in assets
        if isinstance(asset, dict)
        and isinstance(asset.get("browser_download_url"), str)
    }
    for name in ASSET_NAMES:
        if name in download_urls:
            return tag_name, download_urls[name]
    raise ValueError(f"The latest release does not contain {ASSET_NAMES[0]}")


def download_update(download_url: str) -> Path:
    download_path = Path(tempfile.gettempdir()) / f"{APP_NAME}-update.exe"
    request = Request(
        download_url,
        headers={"Accept": "application/octet-stream"},
    )
    with urlopen(request, timeout=60) as response, download_path.open("wb") as output:
        while chunk := response.read(1024 * 1024):
            output.write(chunk)
    return download_path


def install_update(download_path: Path) -> None:
    current_exe = Path(sys.executable).resolve()
    updater_path = Path(tempfile.gettempdir()) / f"{APP_NAME}-updater.bat"
    updater_path.write_text(
        "@echo off\r\n"
        "set attempts=0\r\n"
        ":wait_for_exit\r\n"
        "timeout /t 1 /nobreak >nul\r\n"
        f'copy /y "{download_path}" "{current_exe}" >nul\r\n'
        "if not errorlevel 1 goto start_app\r\n"
        "set /a attempts+=1\r\n"
        "if %attempts% GEQ 30 goto update_failed\r\n"
        "goto wait_for_exit\r\n"
        ":start_app\r\n"
        f'start "" /d "{current_exe.parent}" "{current_exe}"\r\n'
        "del \"%~f0\"\r\n"
        "exit /b 0\r\n"
        ":update_failed\r\n"
        f'del "{download_path}"\r\n'
        f'del "%~f0"\r\n',
        encoding="utf-8",
    )
    subprocess.Popen(
        ["cmd", "/c", str(updater_path)],
        creationflags=subprocess.CREATE_NO_WINDOW,
    )

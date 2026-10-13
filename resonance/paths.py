from __future__ import annotations

import os
import shutil
from pathlib import Path

from .constants import APP_NAME

DATA_ROOT: Path = Path(os.environ.get("LOCALAPPDATA", Path.home()))
# Settings, to-dos, events, commands and the Spotify login token.
DATA_DIR: Path = DATA_ROOT / APP_NAME
# The app was called Resonance before; its data folder moves across.
LEGACY_DATA_DIR: Path = DATA_ROOT / "Resonance"


def prepare_data_dir() -> None:
    """Create the data folder, moving a pre-rename one into place."""
    if not DATA_DIR.exists() and LEGACY_DATA_DIR.is_dir():
        try:
            LEGACY_DATA_DIR.rename(DATA_DIR)
        except OSError:
            # Renaming can fail on Windows if a file is in use; copy instead.
            shutil.copytree(LEGACY_DATA_DIR, DATA_DIR)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

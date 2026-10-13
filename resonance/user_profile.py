from __future__ import annotations

import base64
from io import BytesIO

from PIL import Image, ImageOps

from .paths import DATA_DIR
from .store import Collection

PROFILE = Collection("profile", DATA_DIR / "profile.json")
PROFILE_ID = "me"
# The picture syncs as a small greyscale PNG (about 10 KB) inside the
# profile record; each device draws its own ASCII version from it.
AVATAR_SOURCE_SIZE = 96


def profile_data() -> dict:
    return dict(PROFILE.get(PROFILE_ID) or {})


def display_name() -> str:
    return str(profile_data().get("display_name", "")).strip()


def set_display_name(name: str) -> None:
    data = profile_data()
    data["display_name"] = name.strip()
    PROFILE.put(PROFILE_ID, data)


def avatar_source() -> Image.Image | None:
    encoded = profile_data().get("avatar")
    if not isinstance(encoded, str):
        return None
    try:
        return Image.open(BytesIO(base64.b64decode(encoded))).convert("L")
    except (ValueError, OSError):
        return None


def set_avatar(image: Image.Image | None) -> None:
    data = profile_data()
    if image is None:
        data.pop("avatar", None)
    else:
        square = ImageOps.fit(
            ImageOps.exif_transpose(image).convert("L"),
            (AVATAR_SOURCE_SIZE, AVATAR_SOURCE_SIZE),
        )
        buffer = BytesIO()
        square.save(buffer, format="PNG", optimize=True)
        data["avatar"] = base64.b64encode(buffer.getvalue()).decode("ascii")
    PROFILE.put(PROFILE_ID, data)

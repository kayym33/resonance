"""Hub apps: each module in this folder is a page in the hub's menu.

To add an app, create ``apps/<name>.py`` that defines ``APP``::

    from . import HubApp

    class CookbookPage(customtkinter.CTkFrame):
        def __init__(self, parent, app):
            super().__init__(parent, fg_color="transparent")
            ...

    APP = HubApp(name="cookbook", build=CookbookPage, order=50)

``build(parent, app)`` is called the first time the page is opened and
must return a frame parented to ``parent``. The page fills the hub below
the launcher, so pad its contents by ``constants.MARGIN`` at the sides.

A page can also define any of these methods, which the hub calls when
they exist:

- ``on_show()``: the page was just opened.
- ``data_changed(kinds)``: data synced from another device changed;
  ``kinds`` is a set such as ``{"task", "event", "setting"}``.
- ``show_song(song)``, ``show_song_error()`` and ``set_album_art(images)``:
  the same Spotify updates the windows get (see ``app.py``).
- ``refresh_outlines()``: the size changed, so redo ``outline_width``.
- ``go_to_trail(depth)``: a crumb in the header was clicked (see below).

An app with views of its own can show where it is in the header by
calling ``self.winfo_toplevel().set_trail(self, ["recipes", "carbonara"])``,
which reads "t1ld3 / cookbook / recipes / carbonara". Clicking a crumb
calls ``go_to_trail(depth)``: 0 for the app's own name, 1 for "recipes"
and so on. The last crumb is where you are, so it isn't clickable.

Modules whose names start with ``_`` are skipped.
"""
from __future__ import annotations

import importlib
import pkgutil
import sys
import traceback
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

import customtkinter

if TYPE_CHECKING:
    from ..app import ResonanceApp


@dataclass(frozen=True)
class HubApp:
    # Shown in the menu and typed in the launcher to open the page.
    name: str
    build: Callable[[customtkinter.CTkFrame, ResonanceApp], customtkinter.CTkFrame]
    # Lower comes first in the menu; ties sort by name.
    order: int = 100
    # Shown next to the name in launcher suggestions.
    description: str = ""


def discover() -> list[HubApp]:
    """Import every app module in this folder, in menu order."""
    found: list[HubApp] = []
    for module_info in pkgutil.iter_modules(__path__):
        if module_info.name.startswith("_"):
            continue
        try:
            module = importlib.import_module(f"{__name__}.{module_info.name}")
        except Exception:
            # One broken app shouldn't stop the hub from opening.
            print(f"Skipping app {module_info.name}:", file=sys.stderr)
            traceback.print_exc()
            continue
        hub_app = getattr(module, "APP", None)
        if isinstance(hub_app, HubApp):
            clash = next((other for other in found if other.name == hub_app.name), None)
            if clash is None:
                found.append(hub_app)
            else:
                # Pages are looked up by name, so a second one would hide
                # the first.
                print(
                    f"Skipping app {module_info.name}: another app is "
                    f"already called {hub_app.name!r}",
                    file=sys.stderr,
                )
        else:
            print(
                f"Skipping app {module_info.name}: it doesn't define APP",
                file=sys.stderr,
            )
    return sorted(found, key=lambda hub_app: (hub_app.order, hub_app.name))

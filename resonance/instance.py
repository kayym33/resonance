"""Keep the app to one running copy.

A second launch (for example from a desktop keyboard shortcut) asks the
running copy to show its hub, then exits. Only the standard library is
imported so the handoff stays quick.
"""

from __future__ import annotations

import os
import socket
import threading
from typing import Callable

PORT = 47917
REQUEST = b"t1ld3:show-hub\n"
REPLY = b"t1ld3:ok\n"


def notify_running_instance() -> bool:
    """Return True if another copy is running and will show its hub."""
    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=0.5) as conn:
            conn.sendall(REQUEST)
            return conn.recv(len(REPLY)) == REPLY
    except OSError:
        return False


def listen(on_show_hub: Callable[[], None]) -> socket.socket | None:
    """Serve show-hub requests on a background thread.

    ``on_show_hub`` runs on that thread, so it must hand off to Tk with
    ``after``. Returns the server socket to close on exit, or None if the
    port is taken.
    """
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if os.name != "nt":
        # On Windows this option would let two copies share the port.
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind(("127.0.0.1", PORT))
        server.listen()
    except OSError:
        server.close()
        return None

    def serve() -> None:
        while True:
            try:
                conn, _address = server.accept()
            except OSError:
                return
            with conn:
                conn.settimeout(1)
                try:
                    if conn.recv(len(REQUEST)) != REQUEST:
                        continue
                    conn.sendall(REPLY)
                except OSError:
                    continue
            on_show_hub()

    threading.Thread(target=serve, daemon=True).start()
    return server

"""Keeps the local collections and the user's Supabase rows in step.

A sync uploads every dirty record (the server keeps whichever edit is
newest), then downloads rows stored since the last sync and merges them
the same way. It runs after local edits, every minute, and on sign-in.
Network work happens on the worker pool; collections are only touched
on the Tk thread.
"""

from __future__ import annotations

import json
import time
from concurrent.futures import Future
from typing import TYPE_CHECKING, Any, Callable

from .cloud import AuthError, Cloud, CloudError, Session
from .launcher import (
    PLATFORM,
    commands_modified_at,
    read_commands_file,
    write_synced_commands,
)
from .paths import DATA_DIR
from .events import EVENTS
from .settings import SETTINGS
from .store import Collection, parse_iso
from .todo import TASKS
from .user_profile import PROFILE

if TYPE_CHECKING:
    from .app import ResonanceApp

SYNC_STATE_PATH = DATA_DIR / "sync.json"
SYNCED: tuple[Collection, ...] = (TASKS, EVENTS, SETTINGS, PROFILE)
SYNC_INTERVAL: int = 60
# Wait this long after an edit, so a burst of edits syncs once.
EDIT_DELAY_MS: int = 2000
PUSH_BATCH: int = 500


def load_state() -> dict[str, Any]:
    try:
        with SYNC_STATE_PATH.open(encoding="utf-8") as state_file:
            state: object = json.load(state_file)
    except (OSError, ValueError):
        return {}
    return state if isinstance(state, dict) else {}


def save_state(state: dict[str, Any]) -> None:
    SYNC_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SYNC_STATE_PATH.open("w", encoding="utf-8") as state_file:
        json.dump(state, state_file, indent=2)


def collection_for(kind: str) -> Collection | None:
    return next((item for item in SYNCED if item.kind == kind), None)


class SyncEngine:
    """Status is one of: "local" (signed out), "syncing", "synced",
    "offline" or "error"."""

    def __init__(self, app: ResonanceApp, cloud: Cloud | None = None) -> None:
        self.app = app
        self.cloud = cloud or Cloud()
        # user_id: whose data is on this device; cursor: newest server
        # time seen; commands_pushed: commands.json date last uploaded.
        self.state: dict[str, Any] = load_state()
        self.busy: bool = False
        self.pending: bool = False
        self.scheduled_id: str | None = None
        self.status: str = "local"
        self.message: str = ""
        self.last_synced: float | None = None
        self.listeners: list[Callable[[], None]] = []
        for collection in SYNCED:
            collection.listeners.append(self.request_sync)
        if self.cloud.signed_in:
            self.app.after(500, self.sync_now)
        self.app.after(SYNC_INTERVAL * 1000, self.periodic_sync)

    @property
    def session(self) -> Session | None:
        return self.cloud.session

    def set_status(self, status: str, message: str = "") -> None:
        self.status, self.message = status, message
        for listener in self.listeners:
            listener()

    # Scheduling

    def request_sync(self) -> None:
        if not self.cloud.signed_in:
            return
        if self.scheduled_id is not None:
            self.app.after_cancel(self.scheduled_id)
        self.scheduled_id = self.app.after(EDIT_DELAY_MS, self.sync_now)

    def periodic_sync(self) -> None:
        self.sync_now()
        self.app.after(SYNC_INTERVAL * 1000, self.periodic_sync)

    def sync_now(self) -> None:
        self.scheduled_id = None
        if not self.cloud.signed_in:
            self.set_status("local")
            return
        if self.busy:
            self.pending = True
            return

        self.busy = True
        outgoing = [
            row for collection in SYNCED for row in collection.dirty_records()
        ]
        commands = self.dirty_commands()
        if commands is not None:
            outgoing.append(commands)
        self.set_status("syncing")
        future: Future[list[dict[str, Any]]] = self.app.worker.submit(
            self.exchange,
            outgoing,
            self.state.get("cursor"),
        )
        future.add_done_callback(
            lambda done: self.app.after(0, self.apply_sync, done, outgoing)
        )

    def exchange(
        self,
        outgoing: list[dict[str, Any]],
        cursor: str | None,
    ) -> list[dict[str, Any]]:
        """Worker thread: upload, then download what's new."""
        for start in range(0, len(outgoing), PUSH_BATCH):
            self.cloud.push(outgoing[start:start + PUSH_BATCH])
        return self.cloud.pull(cursor)

    def apply_sync(
        self,
        future: Future[list[dict[str, Any]]],
        outgoing: list[dict[str, Any]],
    ) -> None:
        self.busy = False
        try:
            rows = future.result()
        except AuthError as error:
            if self.cloud.signed_in:
                self.set_status("error", str(error))
            else:
                self.set_status("local", "signed out, please sign in again")
            return
        except CloudError as error:
            self.set_status("offline", str(error))
            return

        self.mark_pushed(outgoing)
        changed = self.merge(rows)
        if rows:
            newest = max(rows, key=lambda row: parse_iso(row["server_updated_at"]))
            self.state["cursor"] = newest["server_updated_at"]
        save_state(self.state)
        self.last_synced = time.time()
        self.set_status("synced")
        if changed:
            self.app.data_changed(changed)
        if self.pending:
            self.pending = False
            self.sync_now()

    def mark_pushed(self, outgoing: list[dict[str, Any]]) -> None:
        for collection in SYNCED:
            pushed = [row for row in outgoing if row["kind"] == collection.kind]
            if pushed:
                collection.mark_pushed(pushed)
        for row in outgoing:
            if row["kind"] == "commands":
                self.state["commands_pushed"] = row["updated_at"]

    def merge(self, rows: list[dict[str, Any]]) -> set[str]:
        changed: set[str] = set()
        touched: set[Collection] = set()
        for row in rows:
            if row["kind"] == "commands":
                if row["id"] == PLATFORM and self.merge_commands(row):
                    changed.add("commands")
                continue
            collection = collection_for(row["kind"])
            if collection is not None and collection.apply_remote(row):
                changed.add(row["kind"])
                touched.add(collection)
        for collection in touched:
            collection.save()
        return changed

    # Launcher commands sync as a whole file, dated by when it was edited.

    def dirty_commands(self) -> dict[str, Any] | None:
        modified_at = commands_modified_at()
        if modified_at is None or modified_at == self.state.get("commands_pushed"):
            return None
        data = read_commands_file()
        if data is None:
            return None
        return {
            "kind": "commands",
            "id": PLATFORM,
            "data": data,
            "deleted": False,
            "updated_at": modified_at,
        }

    def merge_commands(self, row: dict[str, Any]) -> bool:
        modified_at = commands_modified_at()
        if row.get("deleted") or (
            modified_at is not None
            and parse_iso(modified_at) >= parse_iso(row["updated_at"])
        ):
            return False
        self.state["commands_pushed"] = write_synced_commands(
            row["data"],
            row["updated_at"],
        )
        return True

    # Accounts

    def sign_in(
        self,
        email: str,
        password: str,
        on_done: Callable[[str | None], None],
        confirm_switch: Callable[[], bool],
    ) -> None:
        """Sign in on the worker pool; ``on_done`` gets an error or None.

        ``confirm_switch`` asks whether to replace this device's data when
        a different account than last time signs in.
        """
        future: Future[Session] = self.app.worker.submit(
            self.cloud.sign_in,
            email.strip(),
            password,
        )
        future.add_done_callback(
            lambda done: self.app.after(
                0,
                self.finish_sign_in,
                done,
                on_done,
                confirm_switch,
            )
        )

    def finish_sign_in(
        self,
        future: Future[Session],
        on_done: Callable[[str | None], None],
        confirm_switch: Callable[[], bool],
    ) -> None:
        try:
            session = future.result()
        except CloudError as error:
            on_done(str(error))
            return

        previous_user = self.state.get("user_id")
        if previous_user != session.user_id:
            if previous_user is not None:
                if not confirm_switch():
                    self.sign_out()
                    on_done("cancelled")
                    return
                # This device held another account's data: start fresh.
                for collection in SYNCED:
                    collection.clear()
                self.app.data_changed({c.kind for c in SYNCED})
            else:
                # First sign-in here: upload everything made so far.
                for collection in SYNCED:
                    collection.mark_all_dirty()
            self.state = {"user_id": session.user_id}
            save_state(self.state)
        on_done(None)
        self.sync_now()

    def sign_out(self) -> None:
        self.app.worker.submit(self.cloud.revoke, self.cloud.forget_session())
        self.set_status("local")

    def change_password(
        self,
        password: str,
        on_done: Callable[[str | None], None],
    ) -> None:
        future: Future[None] = self.app.worker.submit(
            self.cloud.change_password,
            password,
        )

        def finished(done: Future[None]) -> None:
            try:
                done.result()
            except CloudError as error:
                on_done(str(error))
                return
            on_done(None)

        future.add_done_callback(lambda done: self.app.after(0, finished, done))

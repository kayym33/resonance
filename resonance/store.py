"""Local copies of synced data: one JSON file per kind of record.

Every record keeps when it was last edited, whether it was deleted (kept
as a tombstone so the deletion syncs) and whether it still needs
uploading ("dirty"). The app works entirely from these files; the sync
engine uploads dirty records and merges newer ones from other devices.

Only touch collections from the Tk thread.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

FORMAT_VERSION = 2


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


@dataclass
class Record:
    data: dict[str, Any]
    updated_at: str
    deleted: bool = False
    dirty: bool = False


class Collection:
    def __init__(
        self,
        kind: str,
        path: Path,
        legacy: Callable[[object], dict[str, dict[str, Any]]] | None = None,
    ) -> None:
        """``legacy`` converts a file from before syncing into {id: data}."""
        self.kind = kind
        self.path = path
        self.records: dict[str, Record] = {}
        # Called after local edits (not after merging remote ones).
        self.listeners: list[Callable[[], None]] = []
        self.load(legacy)

    def load(
        self,
        legacy: Callable[[object], dict[str, dict[str, Any]]] | None,
    ) -> None:
        try:
            with self.path.open(encoding="utf-8") as data_file:
                raw: object = json.load(data_file)
        except (OSError, ValueError):
            return
        if isinstance(raw, dict) and raw.get("version") == FORMAT_VERSION:
            for record_id, record in raw.get("records", {}).items():
                self.records[record_id] = Record(
                    data=record.get("data", {}),
                    updated_at=record["updated_at"],
                    deleted=bool(record.get("deleted")),
                    dirty=bool(record.get("dirty")),
                )
        elif legacy is not None:
            stamp = now_iso()
            for record_id, data in legacy(raw).items():
                self.records[record_id] = Record(data, stamp, dirty=True)
            self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as data_file:
            json.dump(
                {
                    "version": FORMAT_VERSION,
                    "records": {
                        record_id: {
                            "data": record.data,
                            "updated_at": record.updated_at,
                            "deleted": record.deleted,
                            "dirty": record.dirty,
                        }
                        for record_id, record in self.records.items()
                    },
                },
                data_file,
                indent=2,
            )

    # Reading and local edits

    def items(self) -> list[tuple[str, dict[str, Any]]]:
        return [
            (record_id, record.data)
            for record_id, record in self.records.items()
            if not record.deleted
        ]

    def get(self, record_id: str) -> dict[str, Any] | None:
        record = self.records.get(record_id)
        return None if record is None or record.deleted else record.data

    def put(self, record_id: str, data: dict[str, Any]) -> None:
        self.records[record_id] = Record(dict(data), now_iso(), dirty=True)
        self.save()
        self.notify()

    def delete(self, record_id: str) -> None:
        if self.get(record_id) is None:
            return
        self.records[record_id] = Record({}, now_iso(), deleted=True, dirty=True)
        self.save()
        self.notify()

    def notify(self) -> None:
        for listener in self.listeners:
            listener()

    # Sync

    def dirty_records(self) -> list[dict[str, Any]]:
        return [
            {
                "kind": self.kind,
                "id": record_id,
                "data": record.data,
                "deleted": record.deleted,
                "updated_at": record.updated_at,
            }
            for record_id, record in self.records.items()
            if record.dirty
        ]

    def mark_pushed(self, pushed: list[dict[str, Any]]) -> None:
        """Clear dirty flags, unless the record changed again meanwhile."""
        for row in pushed:
            record = self.records.get(row["id"])
            if record is not None and record.updated_at == row["updated_at"]:
                record.dirty = False
        self.save()

    def apply_remote(self, row: dict[str, Any]) -> bool:
        """Merge one row from the server; True if the local copy changed."""
        local = self.records.get(row["id"])
        if local is not None and parse_iso(local.updated_at) >= parse_iso(
            row["updated_at"]
        ):
            return False
        self.records[row["id"]] = Record(
            data=row.get("data") or {},
            updated_at=row["updated_at"],
            deleted=bool(row.get("deleted")),
        )
        return True

    def mark_all_dirty(self) -> None:
        for record in self.records.values():
            record.dirty = True
        self.save()

    def clear(self) -> None:
        self.records = {}
        self.save()

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from .paths import DATA_DIR
from .store import Collection, now_iso


@dataclass
class Task:
    id: str
    text: str
    done: bool
    created_at: str


def legacy_tasks(raw: object) -> dict[str, dict[str, Any]]:
    """Convert the pre-sync list of {"text", "done"}, keeping its order."""
    if not isinstance(raw, list):
        return {}
    start = datetime.now(timezone.utc)
    return {
        uuid.uuid4().hex: {
            "text": str(item["text"]),
            "done": bool(item.get("done")),
            "created_at": (start + timedelta(microseconds=index)).isoformat(),
        }
        for index, item in enumerate(raw)
        if isinstance(item, dict) and item.get("text")
    }


TASKS = Collection("task", DATA_DIR / "todo.json", legacy_tasks)


def load_tasks() -> list[Task]:
    tasks = [
        Task(
            id=task_id,
            text=str(data.get("text", "")),
            done=bool(data.get("done")),
            created_at=str(data.get("created_at", "")),
        )
        for task_id, data in TASKS.items()
    ]
    return sorted(tasks, key=lambda task: task.created_at)


def save_task(task: Task) -> None:
    TASKS.put(
        task.id,
        {"text": task.text, "done": task.done, "created_at": task.created_at},
    )


def add_task(text: str) -> None:
    save_task(Task(uuid.uuid4().hex, text, False, now_iso()))


def delete_task(task: Task) -> None:
    TASKS.delete(task.id)

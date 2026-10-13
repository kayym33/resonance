from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from .paths import DATA_DIR

TODO_PATH = DATA_DIR / "todo.json"


@dataclass
class Task:
    text: str
    done: bool = False


def load_tasks() -> list[Task]:
    try:
        with TODO_PATH.open(encoding="utf-8") as todo_file:
            data: object = json.load(todo_file)
    except (OSError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    return [
        Task(str(item["text"]), bool(item.get("done", False)))
        for item in data
        if isinstance(item, dict) and item.get("text")
    ]


def save_tasks(tasks: list[Task]) -> None:
    TODO_PATH.parent.mkdir(parents=True, exist_ok=True)
    with TODO_PATH.open("w", encoding="utf-8") as todo_file:
        json.dump([asdict(task) for task in tasks], todo_file, indent=2)

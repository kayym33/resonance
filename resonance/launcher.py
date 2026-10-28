from __future__ import annotations

import ast
import json
import operator
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from .constants import APP_NAME
from .paths import DATA_DIR
from .store import parse_iso

COMMANDS_PATH = DATA_DIR / "commands.json"
# Commands sync per platform, since program names and paths differ.
PLATFORM = "windows" if os.name == "nt" else "linux"
MAX_SUGGESTIONS = 6

# Written to commands.json on first run so the user can edit them.
# Each "run" entry is one program to start. "{args}" is whatever follows
# the command word, "{query}" is the same text URL-encoded, and a leading
# "~" expands to the home folder. "complete" names a folder whose
# subfolders are suggested as the argument.
if os.name == "nt":
    DEFAULT_COMMANDS: dict[str, dict[str, Any]] = {
        "zen": {
            "description": "Zen browser",
            "run": [[r"C:\Program Files\Zen Browser\zen.exe"]],
        },
        "term": {"description": "terminal", "run": [["wt"]]},
        "projects": {
            "description": "project in a terminal and VS Code",
            "aliases": ["p"],
            "complete": "~/Projects",
            "run": [
                ["wt", "-d", "~/Projects/{args}"],
                ["code", "~/Projects/{args}"],
            ],
        },
        "files": {
            "description": "file explorer",
            "complete": "~",
            "run": [["explorer", "~/{args}"]],
        },
    }
else:
    DEFAULT_COMMANDS = {
        "zen": {"description": "Zen browser", "run": [["zen"]]},
        "term": {"description": "terminal", "run": [["gnome-terminal"]]},
        "projects": {
            "description": "project in a terminal and VS Code",
            "aliases": ["p"],
            "complete": "~/Projects",
            "run": [
                ["gnome-terminal", "--working-directory=~/Projects/{args}"],
                ["code", "~/Projects/{args}"],
            ],
        },
        "files": {
            "description": "file manager",
            "complete": "~",
            "run": [["xdg-open", "~/{args}"]],
        },
    }
BROWSER: list[str] = DEFAULT_COMMANDS["zen"]["run"][0]
DEFAULT_COMMANDS["g"] = {
    "description": "search the web",
    "run": [[*BROWSER, "https://www.google.com/search?q={query}"]],
}
DEFAULT_COMMANDS["yt"] = {
    "description": "search YouTube",
    "run": [[*BROWSER, "https://www.youtube.com/results?search_query={query}"]],
}

# Handled by the app rather than by starting a program.
BUILTINS: dict[str, str] = {
    "player": "pop out the player",
    "play": "play a song on Spotify",
    "todo": "add a to-do",
    "phone": "send a note to your phone",
    "cal": "open the calendar",
    "home": "back to the home page",
    "account": "sign in or manage your account",
    "theme": "switch between auto, night and day",
    "fullscreen": "toggle full screen (F11)",
    "quit": f"quit {APP_NAME}",
}


@dataclass(frozen=True)
class Command:
    name: str
    description: str
    run: tuple[tuple[str, ...], ...]
    aliases: tuple[str, ...] = ()
    complete: str | None = None

    def names(self) -> tuple[str, ...]:
        return (self.name, *self.aliases)


@dataclass(frozen=True)
class Suggestion:
    """One row in the launcher list.

    ``kind`` is "run" (start ``command`` with ``args``), "builtin" (app
    action named by ``args``), "page" (open the hub app named ``args``),
    "play" (Spotify search for ``args``), "todo" (add ``args`` as a task),
    "phone" (push ``args`` to the phone app) or "calc" (``args`` is the
    result).
    """

    title: str
    detail: str
    completion: str
    kind: str
    args: str = ""
    command: Command | None = None


def load_commands() -> list[Command]:
    if not COMMANDS_PATH.exists():
        COMMANDS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with COMMANDS_PATH.open("w", encoding="utf-8") as commands_file:
            json.dump(DEFAULT_COMMANDS, commands_file, indent=2)
        # Date the defaults to 1970 so commands synced from another device
        # always win over them.
        os.utime(COMMANDS_PATH, (0, 0))

    with COMMANDS_PATH.open(encoding="utf-8") as commands_file:
        data: object = json.load(commands_file)
    if not isinstance(data, dict):
        raise ValueError(f"{COMMANDS_PATH} must contain a JSON object")

    commands: list[Command] = []
    for name, entry in data.items():
        if not isinstance(entry, dict) or not entry.get("run"):
            raise ValueError(f'command "{name}" needs a "run" list')
        commands.append(
            Command(
                name=name,
                description=str(entry.get("description", "")),
                run=tuple(tuple(str(arg) for arg in argv) for argv in entry["run"]),
                aliases=tuple(entry.get("aliases", ())),
                complete=entry.get("complete"),
            )
        )
    return commands


def commands_modified_at() -> str | None:
    """When commands.json was last edited, as an ISO timestamp."""
    try:
        modified = COMMANDS_PATH.stat().st_mtime
    except OSError:
        return None
    return datetime.fromtimestamp(modified, timezone.utc).isoformat()


def read_commands_file() -> dict[str, Any] | None:
    try:
        with COMMANDS_PATH.open(encoding="utf-8") as commands_file:
            data: object = json.load(commands_file)
    except (OSError, ValueError):
        return None  # Missing, or mid-edit; try again next sync.
    return data if isinstance(data, dict) else None


def write_synced_commands(data: dict[str, Any], updated_at: str) -> str | None:
    """Save commands from another device, dated to when they were edited
    there so this device doesn't upload them again as a new edit."""
    with COMMANDS_PATH.open("w", encoding="utf-8") as commands_file:
        json.dump(data, commands_file, indent=2)
    stamp = parse_iso(updated_at).timestamp()
    os.utime(COMMANDS_PATH, (stamp, stamp))
    return commands_modified_at()


def expand_arg(template: str, args: str) -> str:
    arg = template.replace("{args}", args).replace("{query}", quote_plus(args))
    if "~" not in template:
        return arg
    # Expand "~" at the start of the argument or after "=" (as in flags).
    home = str(Path.home())
    arg = re.sub(r"(^|=)~", lambda match: match.group(1) + home, arg)
    prefix, separator, path = arg.rpartition("=")
    return f"{prefix}{separator}{os.path.normpath(path)}"


def run_command(command: Command, args: str) -> str:
    """Start every program for a command; returns a status message."""
    for template in command.run:
        argv = [expand_arg(part, args) for part in template]
        program = shutil.which(argv[0])
        if program is None:
            raise FileNotFoundError(f'couldn\'t find "{argv[0]}"')
        kwargs: dict[str, Any] = {
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "cwd": Path.home(),
        }
        if os.name == "nt":
            kwargs["creationflags"] = (
                subprocess.CREATE_NEW_PROCESS_GROUP
                | subprocess.DETACHED_PROCESS
            )
        else:
            kwargs["start_new_session"] = True
        subprocess.Popen([program, *argv[1:]], **kwargs)
    return f"opened {command.name} {args}".rstrip()


def subfolders(folder: str) -> list[str]:
    try:
        return sorted(
            entry.name
            for entry in Path(folder).expanduser().iterdir()
            if entry.is_dir() and not entry.name.startswith(".")
        )
    except OSError:
        return []


def match_rank(text: str, names: tuple[str, ...], description: str) -> int | None:
    """Lower is better; None means no match."""
    if text in names:
        return 0
    if any(name.startswith(text) for name in names):
        return 1
    if any(text in name for name in names):
        return 2
    if text in description.lower():
        return 3
    return None


def suggest(
    text: str,
    commands: list[Command],
    pages: dict[str, str] | None = None,
) -> list[Suggestion]:
    """Rank what ``text`` could mean. ``pages`` maps the hub's app names
    to their descriptions."""
    stripped = text.strip()
    if not stripped:
        return []

    if stripped.startswith("="):
        result = calculate(stripped[1:])
        if result is None:
            return [Suggestion(stripped, "keep typing a sum", stripped, "none")]
        return [Suggestion(f"= {result}", "enter to copy", stripped, "calc", result)]

    word, has_args, args = text.lstrip().partition(" ")
    word = word.lower()
    args = args.strip()
    if has_args:
        if word == "play":
            return [
                Suggestion(
                    f"play {args}" if args else "play",
                    "play on Spotify" if args else "type a song",
                    text,
                    "play" if args else "none",
                    args,
                )
            ]
        if word == "todo":
            return [
                Suggestion(
                    f"todo {args}" if args else "todo",
                    "add to your list" if args else "type a task",
                    text,
                    "todo" if args else "none",
                    args,
                )
            ]
        if word == "phone":
            return [
                Suggestion(
                    f"phone {args}" if args else "phone",
                    "send to your phone" if args else "type a note",
                    text,
                    "phone" if args else "none",
                    args,
                )
            ]
        for command in commands:
            if word in command.names():
                return argument_suggestions(command, word, args)

    ranked: list[tuple[int, int, Suggestion]] = []
    for index, command in enumerate(commands):
        rank = match_rank(stripped.lower(), command.names(), command.description)
        if rank is not None:
            ranked.append(
                (
                    rank,
                    index,
                    Suggestion(
                        command.name,
                        command.description,
                        f"{command.name} ",
                        "run",
                        command=command,
                    ),
                )
            )
    for index, (name, description) in enumerate(BUILTINS.items()):
        rank = match_rank(stripped.lower(), (name,), description)
        if rank is not None:
            ranked.append(
                (
                    rank,
                    len(commands) + index,
                    Suggestion(
                        name,
                        description,
                        f"{name} ",
                        "none" if name in ("play", "todo", "phone") else "builtin",
                        name,
                    ),
                )
            )
    for index, (name, description) in enumerate((pages or {}).items()):
        if name in BUILTINS:
            continue
        detail = description or f"open {name}"
        rank = match_rank(stripped.lower(), (name,), detail)
        if rank is not None:
            ranked.append(
                (
                    rank,
                    len(commands) + len(BUILTINS) + index,
                    Suggestion(name, detail, f"{name} ", "page", name),
                )
            )
    suggestions = [suggestion for *_, suggestion in sorted(ranked)]

    search = next((command for command in commands if command.name == "g"), None)
    if search is not None:
        suggestions.append(
            Suggestion(
                f"g {stripped}",
                "search the web",
                f"g {stripped}",
                "run",
                stripped,
                search,
            )
        )
    return suggestions[:MAX_SUGGESTIONS]


def argument_suggestions(
    command: Command,
    word: str,
    args: str,
) -> list[Suggestion]:
    suggestions = [
        Suggestion(
            f"{word} {args}".rstrip(),
            command.description,
            f"{word} {args}",
            "run",
            args,
            command,
        )
    ]
    if command.complete:
        needle = args.lower()
        for folder in subfolders(command.complete):
            if needle in folder.lower() and folder.lower() != needle:
                suggestions.append(
                    Suggestion(
                        f"{word} {folder}",
                        command.description,
                        f"{word} {folder}",
                        "run",
                        folder,
                        command,
                    )
                )
        # Prefer a folder match over the half-typed name.
        if args and len(suggestions) > 1:
            suggestions.append(suggestions.pop(0))
    return suggestions[:MAX_SUGGESTIONS]


OPERATORS: dict[type, Any] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def calculate(expression: str) -> str | None:
    """Evaluate plain arithmetic safely; None if it isn't valid."""
    try:
        tree = ast.parse(expression.strip().replace("^", "**"), mode="eval")
        value = evaluate(tree.body)
    except (SyntaxError, ValueError, TypeError, ZeroDivisionError, OverflowError):
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if isinstance(value, float):
        return f"{value:.10g}"
    return str(value)


def evaluate(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in OPERATORS:
        left, right = evaluate(node.left), evaluate(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 1000:
            raise ValueError("exponent too large")
        return OPERATORS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in OPERATORS:
        return OPERATORS[type(node.op)](evaluate(node.operand))
    raise ValueError("unsupported expression")

from __future__ import annotations

import tkinter as tk
from concurrent.futures import Future
from typing import TYPE_CHECKING

import customtkinter

from .backend import play_search
from .constants import (
    ACCENT_DARK,
    BACKGROUND,
    INK,
    INK_SOFT,
    MONO_FONT,
    MUTED,
    RULE,
)
from .launcher import (
    COMMANDS_PATH,
    MAX_SUGGESTIONS,
    Command,
    Suggestion,
    load_commands,
    run_command,
    suggest,
)
from .windows import add_rule, cancel_pending_after, outline_width

if TYPE_CHECKING:
    from .app import ResonanceApp

STATUS_CLEAR_TIME: int = 6
NAVIGATION_KEYS = {
    "Up",
    "Down",
    "Return",
    "KP_Enter",
    "Tab",
    "Escape",
    "Shift_L",
    "Shift_R",
    "Control_L",
    "Control_R",
}


def mono(size: int, weight: str = "normal") -> customtkinter.CTkFont:
    return customtkinter.CTkFont(family=MONO_FONT, size=size, weight=weight)


class LauncherPanel(customtkinter.CTkFrame):
    """Command prompt at the top of the hub, with a suggestion dropdown."""

    def __init__(
        self,
        hub: customtkinter.CTkToplevel,
        app: ResonanceApp,
    ) -> None:
        super().__init__(hub, fg_color="transparent")
        self.app: ResonanceApp = app
        self.commands: list[Command] = []
        self.suggestions: list[Suggestion] = []
        self.selected: int = 0
        self.status_id: str | None = None

        self.prompt: customtkinter.CTkFrame = customtkinter.CTkFrame(
            self,
            fg_color="transparent",
        )
        self.prompt.pack(fill="x")
        customtkinter.CTkLabel(
            self.prompt,
            text=">",
            width=14,
            font=mono(16, "bold"),
            text_color=INK,
        ).pack(side="left")
        self.entry: customtkinter.CTkEntry = customtkinter.CTkEntry(
            self.prompt,
            height=34,
            corner_radius=0,
            border_width=0,
            fg_color=BACKGROUND,
            text_color=INK,
            placeholder_text="zen, p resonance, play ..., todo ..., = 12*7",
            placeholder_text_color=MUTED,
            font=mono(14),
        )
        self.entry.pack(side="left", fill="x", expand=True, padx=(8, 0))
        add_rule(self, INK_SOFT)
        self.status_label: customtkinter.CTkLabel = customtkinter.CTkLabel(
            self,
            text="",
            font=mono(10),
            text_color=MUTED,
            anchor="w",
            height=16,
        )
        self.status_label.pack(fill="x", pady=(6, 0))

        # Lives on the hub so it can float over the panels below.
        self.dropdown: customtkinter.CTkFrame = customtkinter.CTkFrame(
            hub,
            fg_color=BACKGROUND,
            border_color=INK,
            border_width=outline_width(self),
            corner_radius=0,
        )
        self.rows: list[
            tuple[
                customtkinter.CTkFrame,
                customtkinter.CTkLabel,
                customtkinter.CTkLabel,
            ]
        ] = []
        for index in range(MAX_SUGGESTIONS):
            row = customtkinter.CTkFrame(
                self.dropdown,
                height=28,
                corner_radius=0,
                fg_color=BACKGROUND,
            )
            title = customtkinter.CTkLabel(
                row,
                text="",
                font=mono(12, "bold"),
                anchor="w",
                height=26,
            )
            title.pack(side="left", padx=(10, 0))
            detail = customtkinter.CTkLabel(
                row,
                text="",
                font=mono(10),
                anchor="e",
                height=26,
            )
            detail.pack(side="right", padx=(0, 10))
            for widget in (row, title, detail):
                widget.bind(
                    "<Button-1>",
                    lambda _event, chosen=index: self.run_suggestion(chosen),
                )
            self.rows.append((row, title, detail))

        self.entry.bind("<KeyRelease>", self.on_key_release)
        self.entry.bind("<FocusIn>", lambda _event: self.reload_commands())
        self.entry.bind("<Down>", lambda _event: self.move_selection(1))
        self.entry.bind("<Up>", lambda _event: self.move_selection(-1))
        self.entry.bind("<Return>", lambda _event: self.run_selected())
        self.entry.bind("<KP_Enter>", lambda _event: self.run_selected())
        self.entry.bind("<Tab>", lambda _event: self.complete_selected())
        self.entry.bind("<Escape>", lambda _event: self.clear())
        self.reload_commands()

    def focus_prompt(self) -> None:
        self.entry.focus_set()

    def reload_commands(self) -> None:
        # Picks up edits to commands.json whenever the prompt is focused.
        try:
            self.commands = load_commands()
        except (OSError, ValueError) as error:
            self.commands = []
            self.show_status(f"{COMMANDS_PATH.name}: {error}", error=True)

    # Suggestions

    def on_key_release(self, event: tk.Event[tk.Misc]) -> None:
        if event.keysym not in NAVIGATION_KEYS:
            self.update_suggestions()

    def update_suggestions(self) -> None:
        self.suggestions = suggest(self.entry.get(), self.commands)
        self.selected = 0
        self.render_suggestions()

    def render_suggestions(self) -> None:
        for row, _title, _detail in self.rows:
            row.pack_forget()
        if not self.suggestions:
            self.dropdown.place_forget()
            return

        for index, suggestion in enumerate(self.suggestions):
            row, title, detail = self.rows[index]
            title.configure(text=suggestion.title)
            detail.configure(text=suggestion.detail)
            row.pack(fill="x", padx=2, pady=(2 if index == 0 else 0, 0))
        self.rows[len(self.suggestions) - 1][0].pack_configure(pady=(0, 2))
        if len(self.suggestions) == 1:
            self.rows[0][0].pack_configure(pady=2)
        self.paint_selection()
        self.dropdown.place(in_=self.prompt, relx=0, rely=1, relwidth=1, y=1)
        self.dropdown.lift()

    def paint_selection(self) -> None:
        for index, (row, title, detail) in enumerate(self.rows):
            selected = index == self.selected
            row.configure(fg_color=INK if selected else BACKGROUND)
            title.configure(text_color=BACKGROUND if selected else INK)
            detail.configure(text_color=RULE if selected else MUTED)

    def move_selection(self, step: int) -> str:
        if self.suggestions:
            self.selected = (self.selected + step) % len(self.suggestions)
            self.paint_selection()
        return "break"

    def complete_selected(self) -> str:
        if self.suggestions:
            completion = self.suggestions[self.selected].completion
            self.entry.delete(0, "end")
            self.entry.insert(0, completion)
            self.entry.icursor("end")
            self.update_suggestions()
        return "break"

    def clear(self) -> str:
        self.entry.delete(0, "end")
        self.update_suggestions()
        return "break"

    # Running

    def run_selected(self) -> str:
        if self.suggestions:
            self.run_suggestion(self.selected)
        return "break"

    def run_suggestion(self, index: int) -> None:
        if index >= len(self.suggestions):
            return
        suggestion = self.suggestions[index]
        if suggestion.kind == "none":
            return
        self.clear()

        if suggestion.kind == "run" and suggestion.command is not None:
            try:
                self.show_status(run_command(suggestion.command, suggestion.args))
            except OSError as error:
                self.show_status(str(error), error=True)
        elif suggestion.kind == "calc":
            self.clipboard_clear()
            self.clipboard_append(suggestion.args)
            self.show_status(f"copied {suggestion.args}")
        elif suggestion.kind == "play":
            self.show_status(f"searching Spotify for {suggestion.args}...")
            future: Future[str] = self.app.worker.submit(
                play_search,
                suggestion.args,
            )
            future.add_done_callback(self.play_request_finished)
        elif suggestion.kind == "todo":
            hub = self.app.hub
            if hub is not None:
                hub.todo_panel.add_task(suggestion.args)
                self.show_status(f"added: {suggestion.args}")
        elif suggestion.args in ("cal", "home") and self.app.hub is not None:
            self.app.hub.show_page("calendar" if suggestion.args == "cal" else "home")
        elif suggestion.args == "player":
            self.app.open_player()
        elif suggestion.args == "quit":
            self.app.quit_app()

    def play_request_finished(self, future: Future[str]) -> None:
        self.after(0, self.apply_play_result, future)

    def apply_play_result(self, future: Future[str]) -> None:
        if not self.winfo_exists():
            return
        try:
            playing = future.result()
        except Exception as error:
            message = str(error).strip().splitlines()[-1] if str(error) else ""
            self.show_status(f"couldn't play: {message[:70]}", error=True)
            return
        self.show_status(f"playing {playing}")
        self.app.after(500, self.app.refresh_song)

    def show_status(self, text: str, error: bool = False) -> None:
        self.status_label.configure(
            text=text,
            text_color=ACCENT_DARK if error else MUTED,
        )
        if self.status_id is not None:
            self.after_cancel(self.status_id)
        self.status_id = self.after(
            STATUS_CLEAR_TIME * 1000,
            lambda: self.status_label.configure(text=""),
        )

    def refresh_outlines(self) -> None:
        self.dropdown.configure(border_width=outline_width(self))

    def destroy(self) -> None:
        cancel_pending_after(self)
        super().destroy()

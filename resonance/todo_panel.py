from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont

import customtkinter

from .constants import BACKGROUND, HOVER, INK, MONO_FONT, MUTED
from .rich_text import RichText, set_font, widget_scaling
from .theme import color, unwatch, watch
from .todo import TASKS, Task, add_task, delete_task, load_tasks, save_task
from .windows import outline_width

TASK_LIST_HEIGHT = 200
# Shown when the list is empty.
EMPTY_ART = (
    "  [x] [x] [x]\n"
    "   all done ~\n"
)


def mono(size: int, weight: str = "normal") -> customtkinter.CTkFont:
    return customtkinter.CTkFont(family=MONO_FONT, size=size, weight=weight)


class TodoPanel(customtkinter.CTkFrame):
    """Hub panel: add, edit, tick off and delete tasks saved in todo.json.

    Clicking (or tapping) a task's text places an entry over it. Enter or
    clicking elsewhere saves; Esc cancels.
    """

    def __init__(
        self,
        parent: customtkinter.CTkFrame,
        list_height: int = TASK_LIST_HEIGHT,
        detailed: bool = False,
    ) -> None:
        super().__init__(parent, fg_color="transparent")
        self.tasks: list[Task] = load_tasks()
        # The to-do app's copy also counts tasks and lists done ones apart.
        self.detailed: bool = detailed
        # The text span of each task in the list, by id, for editing.
        self.text_tags: dict[str, str] = {}
        self.editing: Task | None = None
        self.editor: tk.Entry | None = None
        self.editor_font = tkfont.Font(family=MONO_FONT, size=-12)
        # Set by the click that opens the editor, so its release is ignored.
        self.opening_click: bool = False
        # A reload asked for while editing, done once the edit is over.
        self.reload_pending: bool = False

        header = customtkinter.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x")
        customtkinter.CTkLabel(
            header,
            text="TO DO",
            font=mono(10, "bold"),
            text_color=MUTED,
            anchor="w",
            height=16,
        ).pack(side="left")
        self.count_label: customtkinter.CTkLabel = customtkinter.CTkLabel(
            header,
            text="",
            font=mono(10),
            text_color=MUTED,
            anchor="w",
            height=16,
        )
        if detailed:
            self.count_label.pack(side="left", padx=(12, 0))
        self.clear_button: customtkinter.CTkButton = customtkinter.CTkButton(
            header,
            text="clear done",
            width=80,
            height=16,
            corner_radius=0,
            fg_color="transparent",
            hover_color=HOVER,
            text_color=MUTED,
            font=mono(10),
            command=self.clear_done,
        )

        self.entry: customtkinter.CTkEntry = customtkinter.CTkEntry(
            self,
            height=30,
            corner_radius=0,
            border_width=outline_width(self),
            border_color=INK,
            text_color=INK,
            placeholder_text="+ add a task",
            placeholder_text_color=MUTED,
            font=mono(12),
        )
        self.entry.pack(fill="x", pady=(12, 8))
        self.entry.bind("<Return>", lambda _event: self.add_from_entry())
        self.entry.bind("<KP_Enter>", lambda _event: self.add_from_entry())

        # One text widget for the whole list, which scrolls with the wheel.
        # A CTkScrollableFrame of row widgets took seconds per edit: each
        # row added or removed redrew its scrollbar, which forced another
        # full layout pass (see rich_text.py).
        list_frame = customtkinter.CTkFrame(
            self,
            height=list_height,
            corner_radius=0,
            fg_color="transparent",
        )
        list_frame.pack(fill="x")
        list_frame.pack_propagate(False)
        self.task_list: RichText = RichText(list_frame)
        self.task_list.pack(fill="both", expand=True)
        self.render_tasks()
        # Every edit, from this panel, another copy of it or the launcher,
        # re-renders the list; synced ones arrive through reload.
        TASKS.listeners.append(self.reload)
        # The list swallows its own clicks, and a click elsewhere in the
        # window doesn't move the focus, so both end an edit here. The
        # editor sits over the text, so it closes when the list scrolls or
        # changes size.
        self.task_list.bind("<ButtonRelease-1>", self.click_in_list, add="+")
        self.winfo_toplevel().bind("<Button-1>", self.click_away, add="+")
        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>", "<Configure>"):
            self.task_list.bind(sequence, lambda _event: self.finish_edit(), add="+")

    def add_task(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        add_task(text)

    def add_from_entry(self) -> str:
        self.add_task(self.entry.get())
        self.entry.delete(0, "end")
        return "break"

    def toggle_task(self, task: Task) -> None:
        self.finish_edit()
        task.done = not task.done
        save_task(task)

    def delete_task(self, task: Task) -> None:
        self.finish_edit()
        delete_task(task)

    def clear_done(self) -> None:
        self.finish_edit()
        for task in self.tasks:
            if task.done:
                delete_task(task)

    def reload(self) -> None:
        """Re-read tasks, including ones synced from other devices."""
        if self.editing is not None:
            # Redrawing the list would move the text from under the editor;
            # finish_edit reloads once the edit is over.
            self.reload_pending = True
            return
        self.tasks = load_tasks()
        self.render_tasks()

    def render_tasks(self) -> None:
        self.reload_pending = False
        self.text_tags = {}
        if any(task.done for task in self.tasks):
            self.clear_button.pack(side="right")
        else:
            self.clear_button.pack_forget()

        left = sum(not task.done for task in self.tasks)
        done = len(self.tasks) - left
        count = f"{left} left · {done} done" if done else f"{left} left"
        self.count_label.configure(text=count if self.tasks else "")

        lines = self.task_list
        lines.clear()
        if not self.tasks:
            lines.write(EMPTY_ART, "faded")
            lines.end_text()
            return
        if self.detailed:
            todo = [task for task in self.tasks if not task.done]
            finished = [task for task in self.tasks if task.done]
            self.write_tasks(todo)
            if finished:
                lines.heading("done", first=not todo)
                self.write_tasks(finished)
        else:
            self.write_tasks(self.tasks)
        lines.end_text()

    def write_tasks(self, tasks: list[Task]) -> None:
        lines = self.task_list
        for task in tasks:
            # Tk takes a line's tab stops and spacing from its first
            # character, so every part of the line carries "row".
            line = ("row", "checklist")
            lines.link(
                "[x]" if task.done else "[ ]",
                lambda chosen=task: self.toggle_task(chosen),
                "faded" if task.done else "strong",
                *line,
            )
            lines.write(" ", *line)
            # Touch screens send taps as left clicks, so this covers both.
            lines.link(
                task.text,
                lambda chosen=task.id: self.begin_edit(chosen),
                "faded" if task.done else "body",
                *line,
                *(("struck",) if task.done else ()),
            )
            self.text_tags[task.id] = f"link:{lines.links}"
            lines.write("\t", *line)
            lines.link("x", lambda chosen=task: self.delete_task(chosen), "faded", *line)
            lines.write("\n", *line)

    # Editing in place

    def begin_edit(self, task_id: str) -> None:
        self.finish_edit()  # Saves any other task that was being edited.
        task = next((item for item in self.tasks if item.id == task_id), None)
        tag = self.text_tags.get(task_id)
        if task is None or tag is None:
            return
        lines = self.task_list
        start, end = lines.tag_ranges(tag)

        def measure():  # type: ignore[no-untyped-def]
            return lines.dlineinfo(start), lines.dlineinfo(f"{end} -1c"), lines.bbox(start)

        first, last, box = measure()
        if first is None or last is None or box is None:
            # Partly scrolled out of view. Scrolling it in needs a layout
            # pass before it can be measured, so only pay for one here.
            lines.see(f"{end} -1c")
            lines.see(start)
            lines.update_idletasks()
            first, last, box = measure()
        if first is None or last is None or box is None:
            return
        # From the start of the text to just before the delete button,
        # covering every line a long task wraps onto.
        x = box[0]
        delete_box = lines.bbox(f"{end} +1c")
        right = delete_box[0] if delete_box else lines.winfo_width()
        top = first[1]
        bottom = last[1] + last[3]

        self.editing = task
        self.editor = tk.Entry(lines, bd=0, font=self.editor_font, exportselection=False)
        self.retheme_editor()
        watch(self.retheme_editor)
        self.editor.insert(0, task.text)
        self.editor.icursor("end")
        self.editor.place(x=x, y=top, width=max(1, right - x - 4), height=bottom - top)
        self.editor.bind("<Return>", lambda _event: self.finish_from_key(True))
        self.editor.bind("<KP_Enter>", lambda _event: self.finish_from_key(True))
        self.editor.bind("<Escape>", lambda _event: self.finish_from_key(False))
        self.editor.bind("<FocusOut>", lambda _event: self.finish_edit())
        self.opening_click = True
        # Tk drops a focus request for a widget that isn't on screen yet,
        # and place() maps it when Tk is next idle.
        editor = self.editor
        self.after_idle(lambda: editor.focus_set() if self.editor is editor else None)

    def retheme_editor(self) -> None:
        if self.editor is None:
            return
        scaling = widget_scaling(self)
        set_font(self.editor_font, size=-round(12 * scaling))
        self.editor.configure(
            bg=color(BACKGROUND),
            fg=color(INK),
            insertbackground=color(INK),
            selectbackground=color(HOVER),
            selectforeground=color(INK),
            highlightthickness=max(1, round(scaling)),
            highlightbackground=color(INK),
            highlightcolor=color(INK),
        )

    def click_in_list(self, _event: tk.Event[tk.Misc]) -> None:
        if self.opening_click:
            # The release of the click that opened the editor.
            self.opening_click = False
            return
        # Clicks on a checkbox, a delete button or another task have
        # already finished the edit; this catches the rest of the list.
        self.finish_edit()

    def click_away(self, event: tk.Event[tk.Misc]) -> None:
        if self.editor is not None and event.widget is not self.editor:
            self.finish_edit()

    def finish_from_key(self, save: bool) -> str:
        self.finish_edit(save)
        # Hand the keyboard back to the window so its shortcuts work.
        # "break" keeps Esc from also leaving full screen.
        self.winfo_toplevel().focus_set()
        return "break"

    def finish_edit(self, save: bool = True) -> None:
        """Close the editor. Empty or unchanged text leaves the task as it
        was; anything else is saved through todo.save_task, whose listener
        redraws every copy of the list."""
        task, editor = self.editing, self.editor
        if task is None or editor is None:
            return
        # Cleared first: destroying the editor fires FocusOut, which calls
        # this again.
        self.editing = self.editor = None
        self.opening_click = False
        unwatch(self.retheme_editor)
        text = editor.get().strip()
        editor.destroy()
        if save and text and text != task.text:
            task.text = text
            save_task(task)
        elif self.reload_pending:
            self.reload()

    def refresh_outlines(self) -> None:
        self.finish_edit()
        self.entry.configure(border_width=outline_width(self))
        self.task_list.rescale()

    def destroy(self) -> None:
        # Drop the edit rather than save while the window is coming down.
        if self.editor is not None:
            unwatch(self.retheme_editor)
        self.editing = self.editor = None
        if self.reload in TASKS.listeners:
            TASKS.listeners.remove(self.reload)
        super().destroy()

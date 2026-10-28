from __future__ import annotations

import time
import tkinter as tk
from dataclasses import dataclass
from datetime import date
from tkinter import messagebox
from typing import TYPE_CHECKING, Callable

import customtkinter

from .constants import (
    ACCENT_DARK,
    BACKGROUND,
    HOVER,
    INK,
    INK_SOFT,
    MARGIN,
    MONO_FONT,
    MUTED,
)
from .recipes import (
    CUISINES,
    RECIPES,
    SERVING_CHOICES,
    STARTER_TAGS,
    Recipe,
    cooked_label,
    delete_recipe,
    format_duration,
    format_minutes,
    get_recipe,
    load_recipes,
    parse_ingredients,
    parse_minutes,
    parse_steps,
    parse_tags,
    save_recipe,
    step_timer,
    tag_counts,
)
from .rich_text import ChipCanvas, RichText, TextField, scaled_pad
from .todo import add_task
from .windows import cancel_pending_after, outline_width

if TYPE_CHECKING:
    from .app import ResonanceApp

# Unscaled width of the area inside the page margins.
PAGE_WIDTH = 748
HOME_LEFT_WIDTH = 400
HOME_COLUMN_GAP = 32
INGREDIENT_COLUMN_WIDTH = 270
EDITOR_LEFT_WIDTH = 300
HOME_LIST_LIMIT = 5
TIMER_TICK_MS = 1000
# Finished timers stay in the strip this long unless dismissed.
DONE_TIMER_LINGER_S = 120
TAG_SUGGESTIONS = 10
VIEW_PACK = {"fill": "both", "expand": True, "padx": MARGIN, "pady": (0, 20)}


def mono(
    size: int,
    weight: str = "normal",
    slant: str = "roman",
) -> customtkinter.CTkFont:
    return customtkinter.CTkFont(
        family=MONO_FONT,
        size=size,
        weight=weight,
        slant=slant,
    )


def shorten(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def clear_entry(entry: customtkinter.CTkEntry) -> None:
    """Empty an entry and bring its placeholder back.

    The placeholder is real text in the entry, and CTkEntry only restores
    it after losing focus, so a plain delete would leave the box blank.
    """
    if not entry.get():
        return  # Empty already, or only showing the placeholder.
    entry.delete(0, "end")
    if not str(entry.focus_get() or "").startswith(str(entry)):
        entry.configure(placeholder_text=entry.cget("placeholder_text"))


def format_clock(seconds: float) -> str:
    seconds = max(0, round(seconds))
    hours, rest = divmod(seconds, 3600)
    minutes, seconds = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


@dataclass
class Timer:
    recipe_title: str
    step_number: int
    step: str
    ends_at: float
    done_at: float | None = None


class ServingPicker(customtkinter.CTkFrame):
    """"for [1] [2]": the selected count is drawn filled."""

    def __init__(
        self,
        parent: customtkinter.CTkFrame,
        label: str,
        on_pick: Callable[[int], None],
    ) -> None:
        super().__init__(parent, fg_color="transparent")
        customtkinter.CTkLabel(
            self,
            text=label,
            font=mono(11),
            text_color=MUTED,
        ).pack(side="left", padx=(0, 8))
        self.buttons: dict[int, customtkinter.CTkButton] = {}
        for servings in SERVING_CHOICES:
            button = customtkinter.CTkButton(
                self,
                text=str(servings),
                width=30,
                height=26,
                corner_radius=0,
                border_color=INK,
                font=mono(12, "bold"),
                command=lambda chosen=servings: on_pick(chosen),
            )
            button.pack(side="left", padx=(0, 4))
            self.buttons[servings] = button
        self.set(SERVING_CHOICES[-1])

    def set(self, current: int) -> None:
        for servings, button in self.buttons.items():
            selected = servings == current
            button.configure(
                border_width=0 if selected else outline_width(self),
                fg_color=INK if selected else "transparent",
                hover_color=INK_SOFT if selected else HOVER,
                text_color=BACKGROUND if selected else INK,
            )


class CookbookPage(customtkinter.CTkFrame):
    """Recipes with ingredients that scale for one or two, and a cooking
    mode that walks through the steps with timers.

    Views: home ("/cookbook"), the list ("/cookbook/recipes"), one recipe
    ("/cookbook/recipes/<title>"), its cooking mode and the editor. Each
    view is built the first time it opens and refilled after that:
    making Tk widgets is slow (see rich_text.py), showing built ones isn't.
    Timers belong to the page, so they keep running while you look
    elsewhere.
    """

    def __init__(self, parent: customtkinter.CTkFrame, app: ResonanceApp) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app: ResonanceApp = app
        self.view: str = ""
        self.views: dict[str, customtkinter.CTkFrame] = {}
        self.status_labels: dict[str, customtkinter.CTkLabel] = {}
        self.rich_texts: list[RichText | ChipCanvas | TextField] = []
        self.recipe_id: str | None = None
        self.servings: int = 2
        self.query: str = ""
        self.selected_tags: list[str] = []
        self.step_index: int = 0
        self.timers: list[Timer] = []
        self.timer_tick_id: str | None = None
        self.editing: Recipe | None = None
        self.edit_servings: int = 2
        self.edit_snapshot: tuple[str, ...] = ()
        self.message: tuple[str, bool] | None = None

        # Running timers show above every view; one line each.
        self.timer_text = RichText(self)
        self.rich_texts.append(self.timer_text)

        RECIPES.listeners.append(self.recipes_changed)
        # Cooking mode's keys, bound on the hub (never bind_all). They
        # only act while cooking and when no text field has focus.
        hub = self.winfo_toplevel()
        hub.bind("<Right>", lambda event: self.cooking_key(event, 1), add="+")
        hub.bind("<space>", lambda event: self.cooking_key(event, 1), add="+")
        hub.bind("<Left>", lambda event: self.cooking_key(event, -1), add="+")
        hub.bind("<Control-s>", self.save_shortcut, add="+")
        self.show_home()

    # Navigation

    def go_to_trail(self, depth: int) -> None:
        if depth == 0:
            self.leave_editor_then(self.show_home)
        elif depth == 1:
            self.leave_editor_then(self.show_list)
        elif depth == 2 and self.recipe_id is not None:
            recipe_id = self.recipe_id
            self.leave_editor_then(lambda: self.show_recipe(recipe_id))

    def leave_editor_then(self, action: Callable[[], None]) -> None:
        if self.view == "edit" and self.edit_snapshot != self.form_snapshot():
            if not messagebox.askyesno(
                "Unsaved recipe",
                "Leave without saving this recipe?",
                parent=self.winfo_toplevel(),
            ):
                return
        action()

    def show_view(self, view: str, trail: list[str]) -> None:
        if view not in self.views:
            frame = customtkinter.CTkFrame(self, fg_color="transparent")
            self.views[view] = frame
            status = customtkinter.CTkLabel(
                frame,
                text="",
                font=mono(11),
                text_color=MUTED,
                anchor="w",
                height=18,
            )
            status.pack(side="bottom", fill="x", pady=(8, 0))
            self.status_labels[view] = status
            getattr(self, f"build_{view}")(frame)
        for name, frame in self.views.items():
            if name != view:
                frame.pack_forget()
        if self.views[view].winfo_manager() != "pack":
            self.views[view].pack(**VIEW_PACK)
        self.view = view
        self.show_message()
        self.winfo_toplevel().set_trail(self, trail)

    def recipe_trail(self, recipe: Recipe, *rest: str) -> list[str]:
        # The hub shortens long crumbs to fit the header.
        return ["recipes", recipe.title, *rest]

    def recipes_changed(self) -> None:
        """Local edits refill the browsing views; the editor and cooking
        mode are left alone."""
        if self.view == "home":
            self.fill_home()
        elif self.view == "list":
            self.fill_list()
        elif self.view == "recipe" and self.recipe_id is not None:
            self.show_recipe(self.recipe_id)

    def data_changed(self, kinds: set[str]) -> None:
        if "recipe" in kinds:
            self.recipes_changed()

    def refresh_outlines(self) -> None:
        for widget in self.rich_texts:
            if isinstance(widget, ChipCanvas):
                widget.redraw()
            else:
                widget.rescale()

    def flash(self, text: str, error: bool = False) -> None:
        """A one-line message shown at the bottom of the next view."""
        self.message = (text, error)

    def show_message(self) -> None:
        label = self.status_labels.get(self.view)
        if label is None:
            return
        text, error = self.message or ("", False)
        self.message = None
        label.configure(text=text, text_color=ACCENT_DARK if error else MUTED)

    # Shared widgets

    def heading(self, parent: customtkinter.CTkFrame, text: str) -> None:
        customtkinter.CTkLabel(
            parent,
            text=text.upper(),
            font=mono(10, "bold"),
            text_color=MUTED,
            anchor="w",
            height=16,
        ).pack(fill="x")

    def button(
        self,
        parent: customtkinter.CTkFrame,
        text: str,
        command: Callable[[], None],
        solid: bool = False,
        side: str = "left",
        padx: tuple[int, int] = (0, 8),
        text_color: tuple[str, str] | None = None,
        pack: bool = True,
    ) -> customtkinter.CTkButton:
        button = customtkinter.CTkButton(
            parent,
            text=text,
            width=len(text) * 8 + 28,
            height=32,
            corner_radius=0,
            border_width=0 if solid else outline_width(self),
            border_color=INK,
            fg_color=INK if solid else "transparent",
            hover_color=INK_SOFT if solid else HOVER,
            text_color=BACKGROUND if solid else text_color or INK,
            font=mono(11, "bold"),
            command=command,
        )
        if pack:
            button.pack(side=side, padx=padx)
        return button

    def rich_text(self, parent: tk.Misc, height: int = 1) -> RichText:
        widget = RichText(parent, height)
        self.rich_texts.append(widget)
        return widget

    def chip_canvas(
        self,
        parent: tk.Misc,
        width: int,
        on_click: Callable[[str], None],
    ) -> ChipCanvas:
        widget = ChipCanvas(parent, width, on_click)
        self.rich_texts.append(widget)
        return widget

    def search_entry(self, parent: customtkinter.CTkFrame) -> customtkinter.CTkEntry:
        return customtkinter.CTkEntry(
            parent,
            height=30,
            corner_radius=0,
            border_width=outline_width(self),
            border_color=INK,
            text_color=INK,
            placeholder_text="search recipes, tags or ingredients",
            placeholder_text_color=MUTED,
            font=mono(12),
        )

    def write_recipe_rows(
        self,
        text: RichText,
        recipes: list[Recipe],
        detail: Callable[[Recipe], str] = Recipe.summary,
    ) -> None:
        for recipe in recipes:
            text.row(
                recipe.id,
                ("★ " if recipe.favourite else "") + recipe.title,
                detail(recipe),
                lambda chosen=recipe.id: self.show_recipe(chosen),
            )

    # Home: /cookbook

    def build_home(self, frame: customtkinter.CTkFrame) -> None:
        top = customtkinter.CTkFrame(frame, fg_color="transparent")
        top.pack(fill="x")
        self.home_count = customtkinter.CTkLabel(
            top,
            text="",
            font=mono(12),
            text_color=INK_SOFT,
        )
        self.home_count.pack(side="left")
        self.button(top, "+ new recipe", self.show_editor, solid=True, side="right", padx=(8, 0))
        self.home_all_button = self.button(
            top, "all recipes ->", self.open_list, side="right", padx=(8, 0)
        )

        self.home_empty = customtkinter.CTkLabel(
            frame,
            text=(
                # Padded to one width: each line of the label is centred.
                "    ~   ~   ~    \n"
                "  .-----------.  \n"
                " =|           |= \n"
                "  '-----------'  \n\n"
                "no recipes yet\n\n"
                "add ingredients one per line, like\n"
                "200 g spaghetti   ·   2 eggs   ·   salt to taste\n"
                "and they'll scale between 1 and 2 servings."
            ),
            font=mono(12),
            text_color=MUTED,
            justify="center",
        )
        self.home_content = customtkinter.CTkFrame(frame, fg_color="transparent")
        search = self.search_entry(self.home_content)
        search.pack(fill="x", pady=(14, 0))
        search.bind("<Return>", lambda _event: self.search_from_home(search))
        search.bind("<KP_Enter>", lambda _event: self.search_from_home(search))
        self.home_search = search

        columns = customtkinter.CTkFrame(self.home_content, fg_color="transparent")
        columns.pack(fill="both", expand=True, pady=(22, 0))
        left = customtkinter.CTkFrame(columns, width=HOME_LEFT_WIDTH, fg_color="transparent")
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        self.home_lists = self.rich_text(left)
        self.home_lists.pack(fill="both", expand=True)
        self.home_tags = self.chip_canvas(
            columns,
            PAGE_WIDTH - HOME_LEFT_WIDTH - HOME_COLUMN_GAP,
            self.open_tag,
        )
        self.home_tags.pack(
            side="left", anchor="n", padx=scaled_pad(self, (HOME_COLUMN_GAP, 0))
        )

    def show_home(self) -> None:
        self.show_view("home", [])
        self.fill_home()

    def fill_home(self) -> None:
        recipes = load_recipes()
        self.home_count.configure(
            text=f"{len(recipes)} recipe{'s' if len(recipes) != 1 else ''}"
        )
        if not recipes:
            self.home_content.pack_forget()
            self.home_all_button.pack_forget()
            self.home_empty.pack(fill="x", pady=(60, 0))
            return
        self.home_empty.pack_forget()
        if self.home_all_button.winfo_manager() != "pack":
            self.home_all_button.pack(side="right", padx=(8, 0))
        if self.home_content.winfo_manager() != "pack":
            self.home_content.pack(fill="both", expand=True)
        clear_entry(self.home_search)

        lists = self.home_lists
        lists.clear()
        favourites = [recipe for recipe in recipes if recipe.favourite]
        lists.heading("favourites", first=True)
        if favourites:
            self.write_recipe_rows(lists, favourites[:HOME_LIST_LIMIT])
        else:
            lists.write("star a recipe to keep it here\n", "muted")
        cooked = sorted(
            (recipe for recipe in recipes if recipe.last_cooked),
            key=lambda recipe: recipe.last_cooked or date.min,
            reverse=True,
        )
        if cooked:
            lists.heading("recently cooked")
            today = date.today()
            self.write_recipe_rows(
                lists,
                cooked[:HOME_LIST_LIMIT],
                lambda recipe: cooked_label(recipe.last_cooked, today),
            )
        lists.end_text()

        counts = tag_counts(recipes)
        dishes = [(tag, f"{tag} {count}") for tag, count in counts.items() if tag not in CUISINES]
        cuisines = [(tag, f"{tag} {count}") for tag, count in counts.items() if tag in CUISINES]
        self.home_tags.set_groups(
            [group for group in (("dishes", dishes), ("cuisines", cuisines)) if group[1]]
        )

    def search_from_home(self, search: customtkinter.CTkEntry) -> str:
        self.query = search.get().strip()
        self.selected_tags = []
        self.show_list()
        return "break"

    def open_list(self) -> None:
        self.query = ""
        self.selected_tags = []
        self.show_list()

    def open_tag(self, tag: str) -> None:
        self.query = ""
        self.selected_tags = [tag]
        self.show_list()

    # List: /cookbook/recipes

    def build_list(self, frame: customtkinter.CTkFrame) -> None:
        top = customtkinter.CTkFrame(frame, fg_color="transparent")
        top.pack(fill="x")
        self.list_search = self.search_entry(top)
        self.list_search.pack(side="left", fill="x", expand=True)
        self.list_search.bind(
            "<KeyRelease>", lambda _event: self.set_query(self.list_search.get())
        )
        self.button(top, "+ new recipe", self.show_editor, solid=True, side="right", padx=(10, 0))
        self.list_tags = self.chip_canvas(frame, PAGE_WIDTH, self.toggle_tag)
        self.list_tags.pack(anchor="w", pady=scaled_pad(self, (10, 0)))
        self.list_count = customtkinter.CTkLabel(
            frame,
            text="",
            font=mono(10, "bold"),
            text_color=MUTED,
            anchor="w",
            height=16,
        )
        self.list_count.pack(fill="x", pady=(14, 4))
        self.list_rows = self.rich_text(frame)
        self.list_rows.pack(fill="both", expand=True)

    def show_list(self) -> None:
        self.show_view("list", ["recipes"])
        clear_entry(self.list_search)
        if self.query:
            self.list_search.insert(0, self.query)
        self.fill_list()
        self.list_search.focus_set()

    def set_query(self, query: str) -> None:
        if query.strip() != self.query:
            self.query = query.strip()
            self.fill_list()

    def toggle_tag(self, tag: str) -> None:
        if tag in self.selected_tags:
            self.selected_tags.remove(tag)
        else:
            self.selected_tags.append(tag)
        self.fill_list()

    def filtered(self, recipes: list[Recipe]) -> list[Recipe]:
        return [
            recipe
            for recipe in recipes
            if recipe.matches(self.query)
            and all(tag in recipe.tags for tag in self.selected_tags)
        ]

    def fill_list(self) -> None:
        recipes = load_recipes()
        self.list_tags.set_groups(
            [("", [(tag, tag) for tag in tag_counts(recipes)])],
            set(self.selected_tags),
        )
        shown = self.filtered(recipes)
        filtered = bool(self.query or self.selected_tags)
        self.list_count.configure(
            text=(
                f"{len(shown)} of {len(recipes)} recipes"
                if filtered
                else f"{len(recipes)} recipes"
            ).upper()
        )
        rows = self.list_rows
        rows.clear()
        self.write_recipe_rows(rows, shown)
        if not shown:
            rows.write("nothing matches ~" if filtered else "no recipes yet ~", "muted")
        rows.end_text()

    # One recipe: /cookbook/recipes/<title>

    def build_recipe(self, frame: customtkinter.CTkFrame) -> None:
        top = customtkinter.CTkFrame(frame, fg_color="transparent")
        top.pack(fill="x")
        self.recipe_title = customtkinter.CTkLabel(
            top,
            text="",
            font=mono(20, "bold"),
            text_color=INK,
            anchor="w",
        )
        self.recipe_title.pack(side="left")
        self.star_button = customtkinter.CTkButton(
            top,
            text="☆",
            width=0,
            height=22,
            corner_radius=0,
            fg_color="transparent",
            hover_color=HOVER,
            font=mono(18),
            command=self.toggle_favourite,
        )
        self.star_button.pack(side="left", padx=(8, 0))
        self.recipe_servings = ServingPicker(top, "for", self.set_servings)
        self.recipe_servings.pack(side="right")
        self.recipe_meta = customtkinter.CTkLabel(
            frame,
            text="",
            font=mono(11),
            text_color=MUTED,
            anchor="w",
        )
        self.recipe_meta.pack(fill="x", pady=(2, 0))

        actions = customtkinter.CTkFrame(frame, fg_color="transparent")
        actions.pack(fill="x", pady=(14, 0))
        self.cook_button = self.button(actions, "cook ->", self.start_cooking, solid=True, pack=False)
        self.edit_button = self.button(actions, "edit", lambda: self.show_editor(self.current_recipe()), pack=False)
        self.shopping_button = self.button(actions, "+ shopping to-do", self.add_shopping, pack=False)

        columns = customtkinter.CTkFrame(frame, fg_color="transparent")
        columns.pack(fill="both", expand=True, pady=(20, 0))
        left = customtkinter.CTkFrame(columns, width=INGREDIENT_COLUMN_WIDTH, fg_color="transparent")
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        self.ingredients_text = self.rich_text(left)
        self.ingredients_text.pack(fill="both", expand=True)
        self.steps_text = self.rich_text(columns)
        self.steps_text.pack(
            side="left", fill="both", expand=True, padx=scaled_pad(self, (28, 0))
        )

    def current_recipe(self) -> Recipe | None:
        return get_recipe(self.recipe_id) if self.recipe_id else None

    def show_recipe(self, recipe_id: str) -> None:
        recipe = get_recipe(recipe_id)
        if recipe is None:
            self.flash("that recipe was deleted")
            self.show_home()
            return
        self.recipe_id = recipe_id
        self.show_view("recipe", self.recipe_trail(recipe))
        self.recipe_title.configure(text=recipe.title)
        self.star_button.configure(
            text="★" if recipe.favourite else "☆",
            text_color=ACCENT_DARK if recipe.favourite else MUTED,
        )
        self.recipe_servings.set(self.servings)
        meta = [recipe.summary(), cooked_label(recipe.last_cooked, date.today())]
        self.recipe_meta.configure(text="  ·  ".join(part for part in meta if part))
        for button in (self.cook_button, self.edit_button, self.shopping_button):
            button.pack_forget()
        if recipe.steps:
            self.cook_button.pack(side="left", padx=(0, 8))
        self.edit_button.pack(side="left", padx=(0, 8))
        if recipe.ingredients:
            self.shopping_button.pack(side="left", padx=(0, 8))

        factor = recipe.factor(self.servings)
        ingredients = self.ingredients_text
        ingredients.clear()
        ingredients.heading("ingredients", first=True)
        if factor != 1:
            ingredients.write(f"scaled from {recipe.servings}\n", "hint", "gap")
        for item in recipe.ingredients:
            ingredients.write(f"·  {item.format(factor)}\n", "body", "gap")
        if not recipe.ingredients:
            ingredients.write("none listed\n", "muted")
        ingredients.end_text()

        steps = self.steps_text
        steps.clear()
        steps.heading("steps", first=True)
        for number, step in enumerate(recipe.steps, start=1):
            steps.write(f"{number:>2}\t", "number", "hang", "gap")
            steps.write(f"{step}\n", "body", "hang", "gap")
        if not recipe.steps:
            steps.write("no steps yet\n", "muted")
        if recipe.notes:
            steps.heading("notes")
            steps.write(recipe.notes + "\n", "body")
        steps.end_text()

    def set_servings(self, servings: int) -> None:
        self.servings = servings
        if self.view == "cooking":
            self.fill_step()
        elif self.recipe_id is not None:
            self.show_recipe(self.recipe_id)

    def toggle_favourite(self) -> None:
        recipe = self.current_recipe()
        if recipe is None:
            return
        recipe.favourite = not recipe.favourite
        # The store's listener refills this view.
        save_recipe(recipe)

    def add_shopping(self) -> None:
        recipe = self.current_recipe()
        if recipe is None:
            return
        factor = recipe.factor(self.servings)
        items = ", ".join(item.format(factor) for item in recipe.ingredients)
        add_task(f"shop for {recipe.title.lower()}: {items}")
        self.flash("added a shopping list to your to-dos")
        self.show_recipe(recipe.id)

    # Cooking: /cookbook/recipes/<title>/cooking

    def build_cooking(self, frame: customtkinter.CTkFrame) -> None:
        top = customtkinter.CTkFrame(frame, fg_color="transparent")
        top.pack(fill="x")
        self.step_count = customtkinter.CTkLabel(
            top,
            text="",
            font=mono(10, "bold"),
            text_color=MUTED,
        )
        self.step_count.pack(side="left")
        # One label for all the dots: ■ done or current, □ to come.
        self.step_dots = customtkinter.CTkLabel(
            top,
            text="",
            font=mono(11),
            text_color=INK,
        )
        self.step_dots.pack(side="left", padx=(14, 0))
        self.cooking_servings = ServingPicker(top, "for", self.set_servings)
        self.cooking_servings.pack(side="right")

        self.step_label = customtkinter.CTkLabel(
            frame,
            text="",
            font=mono(20, "bold"),
            text_color=INK,
            anchor="w",
            justify="left",
            wraplength=PAGE_WIDTH,
        )
        self.step_label.pack(fill="x", pady=(34, 0))
        # The ingredients this step mentions; packed only when there are any.
        self.needed_text = self.rich_text(frame)
        # Empty on steps without a timer, so it mustn't default to 200x200.
        timer_row = customtkinter.CTkFrame(frame, width=1, height=1, fg_color="transparent")
        timer_row.pack(fill="x", pady=(24, 0))
        self.timer_button = self.button(timer_row, "", self.start_step_timer, pack=False)
        self.timer_running = customtkinter.CTkLabel(
            timer_row,
            text="timer running ^",
            font=mono(12),
            text_color=MUTED,
        )

        nav = customtkinter.CTkFrame(frame, fg_color="transparent")
        nav.pack(side="bottom", fill="x")
        customtkinter.CTkLabel(
            nav,
            text="<- / -> or space",
            font=mono(10),
            text_color=MUTED,
        ).pack(side="left")
        self.next_button = self.button(nav, "next ->", lambda: self.move_step(1), solid=True, side="right", padx=(8, 0))
        self.back_button = self.button(nav, "<- back", lambda: self.move_step(-1), pack=False)
        # A faded look at the step after this one, just above the buttons.
        self.next_text = self.rich_text(frame)
        self.next_text.pack(side="bottom", fill="x", pady=scaled_pad(self, (0, 18)))

    def start_cooking(self) -> None:
        recipe = self.current_recipe()
        if recipe is None or not recipe.steps:
            return
        self.step_index = 0
        self.show_view("cooking", self.recipe_trail(recipe, "cooking"))
        self.fill_step()

    def fill_step(self) -> None:
        recipe = self.current_recipe()
        if recipe is None or not recipe.steps:
            self.show_home()
            return
        self.step_index = max(0, min(self.step_index, len(recipe.steps) - 1))
        step = recipe.steps[self.step_index]
        last = self.step_index == len(recipe.steps) - 1

        self.step_count.configure(text=f"STEP {self.step_index + 1} OF {len(recipe.steps)}")
        self.step_dots.configure(
            text=" ".join("■" if index <= self.step_index else "□" for index in range(len(recipe.steps)))
        )
        self.cooking_servings.set(self.servings)
        self.step_label.configure(text=step)
        needed = recipe.ingredients_for_step(step)
        factor = recipe.factor(self.servings)
        text = self.needed_text
        text.clear()
        if needed:
            text.heading("you'll need", first=True)
            for item in needed:
                text.write(f"·  {item.format(factor)}\n", "body", "gap")
            text.end_text()
            if text.winfo_manager() != "pack":
                text.pack(fill="x", pady=scaled_pad(self, (28, 0)), after=self.step_label)
            text.fit_height()
        else:
            text.pack_forget()

        upcoming = self.next_text
        upcoming.clear()
        if last:
            upcoming.write("last step", "hint")
        else:
            upcoming.heading("next", first=True)
            upcoming.write(recipe.steps[self.step_index + 1], "faded")
        upcoming.fit_height()

        self.timer_button.pack_forget()
        self.timer_running.pack_forget()
        seconds = step_timer(step)
        if seconds:
            running = any(
                timer.step_number == self.step_index + 1
                and timer.recipe_title == recipe.title
                and timer.done_at is None
                for timer in self.timers
            )
            if running:
                self.timer_running.pack(side="left")
            else:
                text = f"start {format_duration(seconds)} timer"
                self.timer_button.configure(text=text, width=len(text) * 8 + 28)
                self.timer_button.pack(side="left")

        self.next_button.configure(
            text="done ~" if last else "next ->",
            command=self.finish_cooking if last else lambda: self.move_step(1),
        )
        self.back_button.pack_forget()
        if self.step_index > 0:
            self.back_button.pack(side="right", padx=(8, 0))
        # So the arrow keys reach cooking_key rather than the launcher.
        self.focus_set()

    def move_step(self, delta: int) -> None:
        recipe = self.current_recipe()
        if recipe is None:
            return
        index = self.step_index + delta
        if 0 <= index < len(recipe.steps):
            self.step_index = index
            self.fill_step()

    def cooking_key(self, event: tk.Event[tk.Misc], delta: int) -> str | None:
        if self.view != "cooking" or not self.winfo_ismapped():
            return None
        # Arrow keys in a text field move the cursor instead.
        if isinstance(event.widget, (tk.Entry, tk.Text)) and not isinstance(
            event.widget, RichText
        ):
            return None
        recipe = self.current_recipe()
        if recipe is not None and delta > 0 and self.step_index == len(recipe.steps) - 1:
            self.finish_cooking()
        else:
            self.move_step(delta)
        return "break"

    def finish_cooking(self) -> None:
        recipe = self.current_recipe()
        if recipe is None:
            return
        recipe.last_cooked = date.today()
        save_recipe(recipe)
        self.flash("nice ~ marked as cooked today")
        self.show_recipe(recipe.id)

    # Timers

    def start_step_timer(self) -> None:
        recipe = self.current_recipe()
        if recipe is None:
            return
        seconds = step_timer(recipe.steps[self.step_index])
        if seconds:
            self.start_timer(recipe, self.step_index, seconds)

    def start_timer(self, recipe: Recipe, step_index: int, seconds: int) -> None:
        self.timers.append(
            Timer(
                recipe.title,
                step_index + 1,
                recipe.steps[step_index],
                time.monotonic() + seconds,
            )
        )
        self.tick_timers()
        if self.view == "cooking":
            self.fill_step()

    def dismiss_timer(self, timer: Timer) -> None:
        if timer in self.timers:
            self.timers.remove(timer)
        self.tick_timers()
        if self.view == "cooking":
            self.fill_step()

    def tick_timers(self) -> None:
        if self.timer_tick_id is not None:
            self.after_cancel(self.timer_tick_id)
            self.timer_tick_id = None
        now = time.monotonic()
        for timer in self.timers:
            if timer.done_at is None and now >= timer.ends_at:
                timer.done_at = now
                self.app.notify(
                    f"{timer.recipe_title}: timer done",
                    f"step {timer.step_number}: {shorten(timer.step, 80)}",
                    # So it reaches you away from the desk, too.
                    phone=True,
                )
        self.timers = [
            timer
            for timer in self.timers
            if timer.done_at is None or now - timer.done_at < DONE_TIMER_LINGER_S
        ]
        self.fill_timers(now)
        if self.timers:
            self.timer_tick_id = self.after(TIMER_TICK_MS, self.tick_timers)

    def fill_timers(self, now: float) -> None:
        """One line per timer: the countdown, what it's for, and an x."""
        text = self.timer_text
        if not self.timers:
            text.pack_forget()
            return
        text.clear()
        for index, timer in enumerate(self.timers):
            done = timer.done_at is not None
            clock = "done!" if done else format_clock(timer.ends_at - now)
            tag = f"row:{index}"
            text.commands[tag] = lambda chosen=timer: self.dismiss_timer(chosen)
            text.write(clock, "alert" if done else "clock", "row", tag)
            text.write(f"  {timer.recipe_title} · step {timer.step_number}", "muted", "row", tag)
            text.write("\tx\n", "muted", "row", tag)
        text.end_text()
        if text.winfo_manager() != "pack":
            text.pack(
                fill="x",
                padx=scaled_pad(self, MARGIN),
                pady=scaled_pad(self, (0, 12)),
                before=self.views[self.view],
            )
        text.fit_height()

    # Editor: /cookbook/new or /cookbook/recipes/<title>/edit

    def build_edit(self, frame: customtkinter.CTkFrame) -> None:
        columns = customtkinter.CTkFrame(frame, fg_color="transparent")
        columns.pack(fill="both", expand=True)
        left = customtkinter.CTkFrame(columns, width=EDITOR_LEFT_WIDTH, fg_color="transparent")
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        right = customtkinter.CTkFrame(columns, fg_color="transparent")
        right.pack(side="left", fill="both", expand=True, padx=(28, 0))

        self.title_entry = self.form_entry(left, "title")
        self.edit_serves = ServingPicker(left, "SERVES", self.pick_edit_servings)
        self.edit_serves.pack(anchor="w", pady=(0, 12))
        self.minutes_entry = self.form_entry(left, "time", "25, 90 min, 1h 30")
        self.tags_entry = self.form_entry(left, "tags", "pasta, italian, quick")
        self.tags_entry.bind("<KeyRelease>", lambda _event: self.fill_tag_suggestions(), add="+")
        self.tag_suggestions = self.chip_canvas(left, EDITOR_LEFT_WIDTH, self.add_tag)
        self.tag_suggestions.pack(anchor="w", pady=scaled_pad(self, (0, 12)))
        self.notes_box = self.form_textbox(left, "notes", height=70)

        self.ingredients_box = self.form_textbox(
            right,
            "ingredients · one per line",
            height=150,
            hint="200 g spaghetti  ·  2 eggs  ·  salt to taste",
        )
        self.steps_box = self.form_textbox(
            right,
            "steps · one per line",
            height=170,
            hint="mention a time (\"simmer 10 min\") to get a timer",
        )

        bottom = customtkinter.CTkFrame(frame, fg_color="transparent")
        bottom.pack(fill="x", side="bottom", pady=(8, 0))
        self.error_label = customtkinter.CTkLabel(
            bottom,
            text="",
            font=mono(11),
            text_color=ACCENT_DARK,
            anchor="w",
        )
        self.error_label.pack(side="left")
        self.button(bottom, "save", self.save_editor, solid=True, side="right", padx=(8, 0))
        self.button(bottom, "cancel", self.cancel_editor, side="right", padx=(8, 0))
        self.delete_button = self.button(
            bottom,
            "delete",
            self.delete_editing,
            text_color=ACCENT_DARK,
            pack=False,
        )

    def form_entry(
        self,
        parent: customtkinter.CTkFrame,
        label: str,
        placeholder: str = "",
    ) -> customtkinter.CTkEntry:
        self.heading(parent, label)
        entry = customtkinter.CTkEntry(
            parent,
            height=30,
            corner_radius=0,
            border_width=outline_width(self),
            border_color=INK,
            text_color=INK,
            placeholder_text=placeholder,
            placeholder_text_color=MUTED,
            font=mono(12),
        )
        entry.pack(fill="x", pady=(4, 12))
        return entry

    def form_textbox(
        self,
        parent: customtkinter.CTkFrame,
        label: str,
        height: int,
        hint: str = "",
    ) -> TextField:
        self.heading(parent, label)
        if hint:
            customtkinter.CTkLabel(
                parent,
                text=hint,
                font=mono(10, slant="italic"),
                text_color=MUTED,
                anchor="w",
                height=14,
            ).pack(fill="x")
        box = TextField(parent, height)
        box.pack(fill="x", pady=scaled_pad(self, (4, 12)))
        self.rich_texts.append(box)

        # Tab moves on to the next field instead of typing a tab.
        def next_field(event: tk.Event[tk.Misc]) -> str:
            event.widget.tk_focusNext().focus_set()
            return "break"

        box.bind("<Tab>", next_field)
        return box

    def show_editor(self, recipe: Recipe | None = None) -> None:
        self.editing = recipe
        trail = self.recipe_trail(recipe, "edit") if recipe else ["new recipe"]
        self.show_view("edit", trail)
        if recipe is not None:
            self.recipe_id = recipe.id
        self.error_label.configure(text="")
        self.edit_servings = recipe.servings if recipe else 2
        self.edit_serves.set(self.edit_servings)
        values = (
            (self.title_entry, recipe.title if recipe else ""),
            (self.minutes_entry, format_minutes(recipe.minutes) if recipe and recipe.minutes else ""),
            (self.tags_entry, ", ".join(recipe.tags) if recipe else ""),
        )
        for entry, value in values:
            clear_entry(entry)
            if value:
                entry.insert(0, value)
        boxes = (
            (self.notes_box, recipe.notes if recipe else ""),
            (self.ingredients_box, "\n".join(item.format() for item in recipe.ingredients) if recipe else ""),
            (self.steps_box, "\n".join(recipe.steps) if recipe else ""),
        )
        for box, value in boxes:
            box.delete("1.0", "end")
            box.insert("1.0", value)
            # Ctrl+Z shouldn't bring back the last recipe's text.
            box.edit_reset()
        self.delete_button.pack_forget()
        if recipe is not None:
            self.delete_button.pack(side="right", padx=(8, 0))
        self.fill_tag_suggestions()
        self.edit_snapshot = self.form_snapshot()
        self.after(50, self.title_entry.focus_set)

    def pick_edit_servings(self, servings: int) -> None:
        self.edit_servings = servings
        self.edit_serves.set(servings)

    def fill_tag_suggestions(self) -> None:
        typed = parse_tags(self.tags_entry.get())
        known = list(tag_counts(load_recipes()))
        # Starter tags fill in while the cookbook has few of its own.
        pool = known + [tag for tag in STARTER_TAGS if tag not in known]
        offered = [tag for tag in pool if tag not in typed][:TAG_SUGGESTIONS]
        self.tag_suggestions.set_groups([("", [(tag, f"+ {tag}") for tag in offered])])

    def add_tag(self, tag: str) -> None:
        tags = parse_tags(self.tags_entry.get())
        if tag not in tags:
            tags.append(tag)
        self.tags_entry.delete(0, "end")
        self.tags_entry.insert(0, ", ".join(tags))
        self.fill_tag_suggestions()

    def form_snapshot(self) -> tuple[str, ...]:
        if "edit" not in self.views:
            return ()
        return (
            self.title_entry.get(),
            str(self.edit_servings),
            self.minutes_entry.get(),
            self.tags_entry.get(),
            self.notes_box.get("1.0", "end"),
            self.ingredients_box.get("1.0", "end"),
            self.steps_box.get("1.0", "end"),
        )

    def save_shortcut(self, _event: tk.Event[tk.Misc]) -> str | None:
        if self.view != "edit" or not self.winfo_ismapped():
            return None
        self.save_editor()
        return "break"

    def save_editor(self) -> None:
        title = " ".join(self.title_entry.get().split())
        if not title:
            self.error_label.configure(text="give the recipe a name")
            return
        try:
            minutes = parse_minutes(self.minutes_entry.get())
        except ValueError as error:
            self.error_label.configure(text=str(error))
            return
        recipe = self.editing or Recipe(title)
        recipe.title = title
        recipe.servings = self.edit_servings
        recipe.minutes = minutes
        recipe.tags = parse_tags(self.tags_entry.get())
        recipe.notes = self.notes_box.get("1.0", "end").strip()
        recipe.ingredients = parse_ingredients(self.ingredients_box.get("1.0", "end"))
        recipe.steps = parse_steps(self.steps_box.get("1.0", "end"))
        save_recipe(recipe)
        self.flash("saved ~")
        self.show_recipe(recipe.id)

    def cancel_editor(self) -> None:
        if self.editing is not None:
            recipe_id = self.editing.id
            self.leave_editor_then(lambda: self.show_recipe(recipe_id))
        else:
            self.leave_editor_then(self.show_home)

    def delete_editing(self) -> None:
        recipe = self.editing
        if recipe is None:
            return
        if not messagebox.askyesno(
            "Delete recipe",
            f"Delete {recipe.title}? This can't be undone.",
            parent=self.winfo_toplevel(),
        ):
            return
        # Leave the editor first so the store's listener doesn't refill it.
        self.view = "deleted"
        delete_recipe(recipe)
        self.recipe_id = None
        self.flash(f"deleted {recipe.title}")
        self.show_home()

    def destroy(self) -> None:
        if self.recipes_changed in RECIPES.listeners:
            RECIPES.listeners.remove(self.recipes_changed)
        cancel_pending_after(self)
        super().destroy()

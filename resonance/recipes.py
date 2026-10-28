"""Recipes for the cookbook app: storage, ingredient parsing and scaling.

No UI code. Ingredients are typed one per line ("200 g spaghetti",
"1 1/2 tbsp olive oil", "salt to taste") and stored split into amount,
unit and name, so the recipe can be scaled between one and two servings.
"""
from __future__ import annotations

import math
import re
import uuid
from dataclasses import dataclass, field
from datetime import date
from fractions import Fraction
from typing import Any

from .paths import DATA_DIR
from .store import Collection, now_iso

RECIPES = Collection("recipe", DATA_DIR / "recipes.json")
SERVING_CHOICES = (1, 2)
# Tags in this set are grouped as cuisines; every other tag is a dish type.
CUISINES = frozenset(
    {
        "american", "british", "chinese", "french", "greek", "indian",
        "italian", "japanese", "korean", "mediterranean", "mexican",
        "middle eastern", "scottish", "spanish", "thai", "vietnamese",
    }
)
# Offered while the cookbook has few tags of its own.
STARTER_TAGS = (
    "pasta", "noodles", "rice", "curry", "soup", "salad", "beef", "chicken",
    "fish", "veggie", "breakfast", "baking", "snack", "quick",
    "italian", "japanese", "chinese", "mexican", "indian",
)

UNICODE_FRACTIONS = {
    "½": Fraction(1, 2), "⅓": Fraction(1, 3), "⅔": Fraction(2, 3),
    "¼": Fraction(1, 4), "¾": Fraction(3, 4), "⅛": Fraction(1, 8),
}
# Shown when scaling non-metric amounts, so 1/2 of 1 egg reads "½".
# Words a step uses for a kind of ingredient: "boil the pasta" means the
# spaghetti. For the cooking view's "you'll need".
INGREDIENT_KINDS: dict[str, tuple[str, ...]] = {
    "pasta": (
        "spaghetti", "penne", "linguine", "fusilli", "rigatoni", "tagliatelle",
        "macaroni", "fettuccine", "orzo", "lasagne", "lasagna", "gnocchi",
    ),
    "noodles": ("udon", "soba", "ramen", "noodle"),
    "cheese": (
        "parmesan", "pecorino", "cheddar", "mozzarella", "feta", "gruyere",
        "ricotta", "halloumi", "mascarpone",
    ),
    "herbs": ("basil", "parsley", "coriander", "cilantro", "thyme", "rosemary", "dill", "mint"),
}
NICE_FRACTIONS = {
    Fraction(0): "", Fraction(1, 8): "⅛", Fraction(1, 4): "¼",
    Fraction(1, 3): "⅓", Fraction(1, 2): "½", Fraction(2, 3): "⅔",
    Fraction(3, 4): "¾", Fraction(1): "",
}
# Weighed and measured amounts scale to plain numbers instead.
METRIC_UNITS = frozenset({"g", "kg", "ml", "l"})
# Never pluralised: "2 tbsp", not "2 tbsps".
ABBREVIATED_UNITS = frozenset({"tsp", "tbsp", "oz", "lb"})
UNITS = frozenset(
    {
        "g", "gram", "grams", "kg", "ml", "l", "litre", "litres", "liter",
        "liters", "tsp", "teaspoon", "teaspoons", "tbsp", "tablespoon",
        "tablespoons", "cup", "cups", "clove", "cloves", "can", "cans", "tin",
        "tins", "pinch", "pinches", "handful", "handfuls", "slice", "slices",
        "bunch", "bunches", "pack", "packs", "piece", "pieces", "sprig",
        "sprigs", "stick", "sticks", "oz", "lb",
    }
)
NUMBER = r"(?:\d+\s+\d+/\d+|\d+/\d+|\d+(?:\.\d+)?[½⅓⅔¼¾⅛]?|[½⅓⅔¼¾⅛])"
AMOUNT_PATTERN = re.compile(
    rf"^\s*(?P<amount>{NUMBER})(?:\s*(?:-|–|to)\s*(?P<amount_max>{NUMBER}))?\s*"
)
# "simmer for 10 minutes", "bake 1 hr", "rest 30-40 secs".
TIMER_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)(?:\s*(?:-|–|to)\s*\d+(?:\.\d+)?)?\s*"
    r"(hours?|hrs?|minutes?|mins?|seconds?|secs?)\b",
    re.IGNORECASE,
)
# Leading "1." or "2)" that people type when numbering steps by hand.
STEP_NUMBER = re.compile(r"^\s*\d+\s*[.)]\s*")
MAX_TIMER_SECONDS = 12 * 60 * 60


def parse_number(text: str) -> Fraction:
    text = text.strip()
    if text in UNICODE_FRACTIONS:
        return UNICODE_FRACTIONS[text]
    if text[-1] in UNICODE_FRACTIONS:
        return Fraction(text[:-1]) + UNICODE_FRACTIONS[text[-1]]
    if " " in text:
        whole, part = text.split()
        return Fraction(whole) + Fraction(part)
    return Fraction(text)


@dataclass
class Ingredient:
    name: str
    amount: Fraction | None = None
    # Set for ranges such as "2-3 cloves garlic".
    amount_max: Fraction | None = None
    unit: str = ""

    @classmethod
    def parse(cls, line: str) -> Ingredient:
        """Split "200 g spaghetti" into amount, unit and name. Lines with
        no number ("salt to taste") keep everything in the name."""
        match = AMOUNT_PATTERN.match(line)
        if match is None:
            return cls(line.strip())
        amount = parse_number(match["amount"])
        amount_max = (
            parse_number(match["amount_max"]) if match["amount_max"] else None
        )
        # The pattern also takes the space, so "200g" and "200 g" both
        # leave "g spaghetti" here.
        rest = line[match.end():].strip()
        unit_word, _, name = rest.partition(" ")
        if unit_word.lower().rstrip(".") in UNITS and name:
            return cls(name.strip(), amount, amount_max, unit_word.rstrip("."))
        return cls(rest, amount, amount_max)

    def to_data(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "amount": str(self.amount) if self.amount is not None else None,
            "amount_max": (
                str(self.amount_max) if self.amount_max is not None else None
            ),
            "unit": self.unit,
        }

    @classmethod
    def from_data(cls, data: dict[str, Any]) -> Ingredient:
        def fraction(value: object) -> Fraction | None:
            try:
                return Fraction(str(value)) if value is not None else None
            except (ValueError, ZeroDivisionError):
                return None

        return cls(
            name=str(data.get("name", "")),
            amount=fraction(data.get("amount")),
            amount_max=fraction(data.get("amount_max")),
            unit=str(data.get("unit", "")),
        )

    def format(self, factor: Fraction = Fraction(1)) -> str:
        """The ingredient line with its amount multiplied by ``factor``."""
        if self.amount is None:
            return self.name
        metric = self.unit.lower() in METRIC_UNITS
        amount = format_amount(self.amount * factor, metric)
        if self.amount_max is not None:
            amount += "-" + format_amount(self.amount_max * factor, metric)
        if not self.unit:
            return f"{amount} {match_plural(self.name, self.amount, self.amount * factor)}"
        if metric:
            # Metric units sit against the number, as people write them.
            return f"{amount}{self.unit} {self.name}"
        unit = self.unit
        if unit.lower() not in ABBREVIATED_UNITS:
            unit = match_plural(unit, self.amount, self.amount * factor)
        return f"{amount} {unit} {self.name}"


def match_plural(name: str, before: Fraction, after: Fraction) -> str:
    """Fix the noun when scaling crosses one: "1 egg" doubled is "2 eggs",
    "2 onions" halved is "1 onion". Only the word before any comma
    changes ("1 red onion, diced"); a rough rule for common ingredients."""
    head, comma, rest = name.partition(",")
    words = head.split()
    if not words:
        return name
    word = words[-1]
    if before <= 1 < after:
        word = pluralize(word)
    elif after <= 1 < before:
        word = singularize(word)
    else:
        return name
    return " ".join([*words[:-1], word]) + comma + rest


def pluralize(word: str) -> str:
    lower = word.lower()
    if lower.endswith("s"):
        return word
    if lower.endswith(("sh", "ch", "x", "o")):
        return word + "es"
    if lower.endswith("y") and lower[-2:-1] not in "aeiou":
        return word[:-1] + "ies"
    return word + "s"


def singularize(word: str) -> str:
    lower = word.lower()
    if lower.endswith("ss") or not lower.endswith("s"):
        return word
    if lower.endswith("ies"):
        return word[:-3] + "y"
    if lower.endswith(("shes", "ches", "xes", "oes")):
        return word[:-2]
    return word[:-1]


def format_amount(value: Fraction, metric: bool) -> str:
    if metric:
        if value >= 100:
            # Nobody weighs 112.5 g of pasta. Halves round up (round()
            # would send 112.5 to 110 but 117.5 to 120).
            return str(math.floor(value / 5 + Fraction(1, 2)) * 5)
        # To one decimal place, halves up again: round(0.25, 1) is 0.2.
        tenths = math.floor(value * 10 + Fraction(1, 2))
        return f"{tenths / 10:g}"
    whole = int(value)
    part = value - whole
    nearest = min(NICE_FRACTIONS, key=lambda nice: abs(nice - part))
    if nearest == 1:
        whole, nearest = whole + 1, Fraction(0)
    if whole == 0 and nearest == 0:
        # Scaled down below the smallest nice fraction.
        return "⅛"
    return f"{whole if whole else ''}{NICE_FRACTIONS[nearest]}"


@dataclass
class Recipe:
    title: str
    servings: int = 2
    tags: list[str] = field(default_factory=list)
    minutes: int | None = None
    ingredients: list[Ingredient] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)
    notes: str = ""
    favourite: bool = False
    last_cooked: date | None = None
    created_at: str = field(default_factory=now_iso)
    id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def factor(self, servings: int) -> Fraction:
        return Fraction(servings, self.servings)

    def summary(self) -> str:
        """"pasta · italian · 25 min", for lists."""
        parts = list(self.tags)
        if self.minutes:
            parts.append(format_minutes(self.minutes))
        return " · ".join(parts)

    def matches(self, query: str) -> bool:
        query = query.strip().lower()
        if not query:
            return True
        words = re.findall(
            r"[^\W_]+",
            " ".join(
                [self.title, *self.tags, *(item.name for item in self.ingredients)]
            ).lower(),
        )
        # Each typed word must start a word in the recipe, so "spag" finds
        # spaghetti as you type and "eggs" finds "1 egg", but "egg" doesn't
        # find "veggie".
        return all(
            any(
                word.startswith(typed) or word.startswith(singularize(typed))
                for word in words
            )
            for typed in re.findall(r"[^\W_]+", query)
        )

    def ingredients_for_step(self, step: str) -> list[Ingredient]:
        """Ingredients the step mentions by name, for the cooking view."""
        text = step.lower()
        found = []
        for item in self.ingredients:
            words = re.findall(r"[a-z]+", item.name.lower())
            # "parmesan" in "add the parmesan"; skip short words like "of".
            named = any(len(word) > 3 and word in text for word in words)
            kind = any(
                kind in text and any(word.startswith(kinds) for word in words)
                for kind, kinds in INGREDIENT_KINDS.items()
            )
            if named or kind:
                found.append(item)
        return found


def format_duration(seconds: int) -> str:
    """"30 sec", "5 min", "1 h 30 min"; for timers found in steps."""
    if seconds < 60:
        return f"{seconds} sec"
    minutes, rest = divmod(seconds, 60)
    text = format_minutes(minutes)
    return f"{text} {rest} sec" if rest else text


def format_minutes(minutes: int) -> str:
    if minutes < 60:
        return f"{minutes} min"
    hours, rest = divmod(minutes, 60)
    return f"{hours} h {rest} min" if rest else f"{hours} h"


DURATION_PATTERN = re.compile(
    r"^\s*(?:(\d+)\s*h(?:ours?|rs?)?)?\s*(?:(\d+)\s*(?:m|mins?|minutes?)?)?\s*$",
    re.IGNORECASE,
)


def parse_minutes(text: str) -> int | None:
    """"25", "1h 30" or "90 min" as minutes; None when empty."""
    if not text.strip():
        return None
    match = DURATION_PATTERN.match(text)
    if match is None or not (match[1] or match[2]):
        raise ValueError("write the time like 25, 90 min or 1h 30")
    total = int(match[1] or 0) * 60 + int(match[2] or 0)
    return total or None


def cooked_label(cooked: date | None, today: date) -> str:
    if cooked is None:
        return "not cooked yet"
    days = (today - cooked).days
    if days <= 0:
        return "cooked today"
    if days == 1:
        return "cooked yesterday"
    if days < 14:
        return f"cooked {days} days ago"
    return f"cooked {cooked.day} {cooked:%b}".lower()


def step_timer(step: str) -> int | None:
    """Seconds for the first duration a step mentions, if any. A range
    such as "10-12 minutes" uses the shorter time, to check early."""
    match = TIMER_PATTERN.search(step)
    if match is None:
        return None
    value = float(match[1])
    unit = match[2].lower()
    if unit.startswith("h"):
        seconds = value * 3600
    elif unit.startswith("m"):
        seconds = value * 60
    else:
        seconds = value
    seconds = round(seconds)
    return seconds if 0 < seconds <= MAX_TIMER_SECONDS else None


def clean_tag(tag: str) -> str:
    return " ".join(tag.strip().lower().split())


def parse_tags(text: str) -> list[str]:
    tags: list[str] = []
    for part in text.split(","):
        tag = clean_tag(part)
        if tag and tag not in tags:
            tags.append(tag)
    return tags


def parse_steps(text: str) -> list[str]:
    return [
        STEP_NUMBER.sub("", line).strip()
        for line in text.splitlines()
        if line.strip()
    ]


def parse_ingredients(text: str) -> list[Ingredient]:
    return [
        Ingredient.parse(line.lstrip("-•* ").strip())
        for line in text.splitlines()
        if line.strip().lstrip("-•* ")
    ]


def recipe_data(recipe: Recipe) -> dict[str, Any]:
    return {
        "title": recipe.title,
        "servings": recipe.servings,
        "tags": recipe.tags,
        "minutes": recipe.minutes,
        "ingredients": [item.to_data() for item in recipe.ingredients],
        "steps": recipe.steps,
        "notes": recipe.notes,
        "favourite": recipe.favourite,
        "last_cooked": recipe.last_cooked.isoformat() if recipe.last_cooked else None,
        "created_at": recipe.created_at,
    }


def recipe_from_data(recipe_id: str, data: dict[str, Any]) -> Recipe:
    servings = data.get("servings")
    minutes = data.get("minutes")
    last_cooked = data.get("last_cooked")
    try:
        cooked = date.fromisoformat(last_cooked) if last_cooked else None
    except (TypeError, ValueError):
        cooked = None
    return Recipe(
        id=recipe_id,
        title=str(data.get("title", "")),
        servings=servings if servings in SERVING_CHOICES else 2,
        tags=[clean_tag(str(tag)) for tag in data.get("tags") or []],
        minutes=minutes if isinstance(minutes, int) and minutes > 0 else None,
        ingredients=[
            Ingredient.from_data(item)
            for item in data.get("ingredients") or []
            if isinstance(item, dict)
        ],
        steps=[str(step) for step in data.get("steps") or []],
        notes=str(data.get("notes", "")),
        favourite=bool(data.get("favourite")),
        last_cooked=cooked,
        created_at=str(data.get("created_at", "")),
    )


def load_recipes() -> list[Recipe]:
    recipes = [recipe_from_data(recipe_id, data) for recipe_id, data in RECIPES.items()]
    return sorted(recipes, key=lambda recipe: recipe.title.lower())


def get_recipe(recipe_id: str) -> Recipe | None:
    data = RECIPES.get(recipe_id)
    return recipe_from_data(recipe_id, data) if data is not None else None


def save_recipe(recipe: Recipe) -> None:
    RECIPES.put(recipe.id, recipe_data(recipe))


def delete_recipe(recipe: Recipe) -> None:
    RECIPES.delete(recipe.id)


def tag_counts(recipes: list[Recipe]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for recipe in recipes:
        for tag in recipe.tags:
            counts[tag] = counts.get(tag, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))

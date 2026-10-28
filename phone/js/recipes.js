// Recipes: parsing ingredient lines, scaling them for one or two, and the
// helpers cooking mode uses. A port of resonance/recipes.py, which is the
// reference: phone/tests/parity.mjs checks both give the same answers.

export const SERVING_CHOICES = [1, 2];
export const CUISINES = new Set([
  "american", "british", "chinese", "french", "greek", "indian",
  "italian", "japanese", "korean", "mediterranean", "mexican",
  "middle eastern", "scottish", "spanish", "thai", "vietnamese",
]);

// Exact fractions, like Python's Fraction, so scaling never drifts.
export class Fraction {
  constructor(numerator, denominator = 1) {
    if (denominator === 0) throw new RangeError("zero denominator");
    const sign = denominator < 0 ? -1 : 1;
    const divisor = gcd(Math.abs(numerator), Math.abs(denominator)) || 1;
    this.n = (sign * numerator) / divisor;
    this.d = Math.abs(denominator) / divisor;
  }

  // "3/2", "200", "1.5" (Python's str(Fraction) and what people type).
  static parse(text) {
    text = String(text).trim();
    const slash = text.match(/^(-?\d+)\/(\d+)$/);
    if (slash) return new Fraction(Number(slash[1]), Number(slash[2]));
    const decimal = text.match(/^(-?)(\d*)(?:\.(\d+))?$/);
    if (!decimal || (!decimal[2] && !decimal[3])) throw new RangeError(`not a number: ${text}`);
    const places = (decimal[3] || "").length;
    const digits = Number((decimal[2] || "0") + (decimal[3] || ""));
    return new Fraction((decimal[1] ? -1 : 1) * digits, 10 ** places);
  }

  add(other) { return new Fraction(this.n * other.d + other.n * this.d, this.d * other.d); }
  sub(other) { return new Fraction(this.n * other.d - other.n * this.d, this.d * other.d); }
  mul(other) { return new Fraction(this.n * other.n, this.d * other.d); }
  value() { return this.n / this.d; }
  compare(other) { return this.n * other.d - other.n * this.d; }
  toString() { return this.d === 1 ? String(this.n) : `${this.n}/${this.d}`; }
}

function gcd(a, b) {
  while (b) [a, b] = [b, a % b];
  return a;
}

const ONE = new Fraction(1);
const HALF = new Fraction(1, 2);
const UNICODE_FRACTIONS = {
  "½": new Fraction(1, 2), "⅓": new Fraction(1, 3), "⅔": new Fraction(2, 3),
  "¼": new Fraction(1, 4), "¾": new Fraction(3, 4), "⅛": new Fraction(1, 8),
};
// In order: ties go to the first, as with Python's min().
const NICE_FRACTIONS = [
  [new Fraction(0), ""], [new Fraction(1, 8), "⅛"], [new Fraction(1, 4), "¼"],
  [new Fraction(1, 3), "⅓"], [new Fraction(1, 2), "½"], [new Fraction(2, 3), "⅔"],
  [new Fraction(3, 4), "¾"], [new Fraction(1), ""],
];
const METRIC_UNITS = new Set(["g", "kg", "ml", "l"]);
const ABBREVIATED_UNITS = new Set(["tsp", "tbsp", "oz", "lb"]);
const UNITS = new Set([
  "g", "gram", "grams", "kg", "ml", "l", "litre", "litres", "liter",
  "liters", "tsp", "teaspoon", "teaspoons", "tbsp", "tablespoon",
  "tablespoons", "cup", "cups", "clove", "cloves", "can", "cans", "tin",
  "tins", "pinch", "pinches", "handful", "handfuls", "slice", "slices",
  "bunch", "bunches", "pack", "packs", "piece", "pieces", "sprig",
  "sprigs", "stick", "sticks", "oz", "lb",
]);
const INGREDIENT_KINDS = {
  pasta: [
    "spaghetti", "penne", "linguine", "fusilli", "rigatoni", "tagliatelle",
    "macaroni", "fettuccine", "orzo", "lasagne", "lasagna", "gnocchi",
  ],
  noodles: ["udon", "soba", "ramen", "noodle"],
  cheese: [
    "parmesan", "pecorino", "cheddar", "mozzarella", "feta", "gruyere",
    "ricotta", "halloumi", "mascarpone",
  ],
  herbs: ["basil", "parsley", "coriander", "cilantro", "thyme", "rosemary", "dill", "mint"],
};
const NUMBER = String.raw`(?:\d+\s+\d+/\d+|\d+/\d+|\d+(?:\.\d+)?[½⅓⅔¼¾⅛]?|[½⅓⅔¼¾⅛])`;
const AMOUNT_PATTERN = new RegExp(
  String.raw`^\s*(${NUMBER})(?:\s*(?:-|–|to)\s*(${NUMBER}))?\s*`,
);
const TIMER_PATTERN = /(\d+(?:\.\d+)?)(?:\s*(?:-|–|to)\s*\d+(?:\.\d+)?)?\s*(hours?|hrs?|minutes?|mins?|seconds?|secs?)\b/i;
const STEP_NUMBER = /^\s*\d+\s*[.)]\s*/;
const MAX_TIMER_SECONDS = 12 * 60 * 60;
// Python's [^\W_]+: runs of letters and digits.
const WORD = /[\p{L}\p{N}]+/gu;

function parseNumber(text) {
  text = text.trim();
  if (text in UNICODE_FRACTIONS) return UNICODE_FRACTIONS[text];
  const last = text.at(-1);
  if (last in UNICODE_FRACTIONS) return Fraction.parse(text.slice(0, -1)).add(UNICODE_FRACTIONS[last]);
  if (text.includes(" ")) {
    const [whole, part] = text.split(/\s+/);
    return Fraction.parse(whole).add(Fraction.parse(part));
  }
  return Fraction.parse(text);
}

export class Ingredient {
  constructor(name, amount = null, amountMax = null, unit = "") {
    this.name = name;
    this.amount = amount;
    this.amountMax = amountMax;
    this.unit = unit;
  }

  // "200 g spaghetti" into amount, unit and name. Lines with no number
  // ("salt to taste") keep everything in the name.
  static parse(line) {
    const match = line.match(AMOUNT_PATTERN);
    if (!match) return new Ingredient(line.trim());
    const amount = parseNumber(match[1]);
    const amountMax = match[2] ? parseNumber(match[2]) : null;
    const rest = line.slice(match[0].length).trim();
    const space = rest.indexOf(" ");
    const unitWord = space < 0 ? rest : rest.slice(0, space);
    const name = space < 0 ? "" : rest.slice(space + 1);
    const unit = unitWord.replace(/\.+$/, "");
    if (UNITS.has(unit.toLowerCase()) && name) {
      return new Ingredient(name.trim(), amount, amountMax, unit);
    }
    return new Ingredient(rest, amount, amountMax);
  }

  static fromData(data) {
    const fraction = (value) => {
      try {
        return value === null || value === undefined ? null : Fraction.parse(value);
      } catch {
        return null;
      }
    };
    return new Ingredient(
      String(data.name ?? ""),
      fraction(data.amount),
      fraction(data.amount_max),
      String(data.unit ?? ""),
    );
  }

  toData() {
    return {
      name: this.name,
      amount: this.amount ? this.amount.toString() : null,
      amount_max: this.amountMax ? this.amountMax.toString() : null,
      unit: this.unit,
    };
  }

  // The line with its amount multiplied by factor.
  format(factor = ONE) {
    if (!this.amount) return this.name;
    const metric = METRIC_UNITS.has(this.unit.toLowerCase());
    const scaled = this.amount.mul(factor);
    let amount = formatAmount(scaled, metric);
    if (this.amountMax) amount += "-" + formatAmount(this.amountMax.mul(factor), metric);
    if (!this.unit) return `${amount} ${matchPlural(this.name, this.amount, scaled)}`;
    if (metric) return `${amount}${this.unit} ${this.name}`;
    let unit = this.unit;
    if (!ABBREVIATED_UNITS.has(unit.toLowerCase())) unit = matchPlural(unit, this.amount, scaled);
    return `${amount} ${unit} ${this.name}`;
  }
}

// "1 egg" doubled is "2 eggs", "2 onions" halved is "1 onion". Only the
// word before any comma changes ("1 red onion, diced").
export function matchPlural(name, before, after) {
  const comma = name.indexOf(",");
  const head = comma < 0 ? name : name.slice(0, comma);
  const tail = comma < 0 ? "" : name.slice(comma);
  const words = head.split(/\s+/).filter(Boolean);
  if (!words.length) return name;
  let word = words.at(-1);
  if (before.compare(ONE) <= 0 && after.compare(ONE) > 0) word = pluralize(word);
  else if (after.compare(ONE) <= 0 && before.compare(ONE) > 0) word = singularize(word);
  else return name;
  return [...words.slice(0, -1), word].join(" ") + tail;
}

export function pluralize(word) {
  const lower = word.toLowerCase();
  if (lower.endsWith("s")) return word;
  if (["sh", "ch", "x", "o"].some((end) => lower.endsWith(end))) return word + "es";
  if (lower.endsWith("y") && !"aeiou".includes(lower.at(-2) ?? "a")) return word.slice(0, -1) + "ies";
  return word + "s";
}

export function singularize(word) {
  const lower = word.toLowerCase();
  if (lower.endsWith("ss") || !lower.endsWith("s")) return word;
  if (lower.endsWith("ies")) return word.slice(0, -3) + "y";
  if (["shes", "ches", "xes", "oes"].some((end) => lower.endsWith(end))) return word.slice(0, -2);
  return word.slice(0, -1);
}

function floorFraction(value) {
  return Math.floor(value.n / value.d);
}

export function formatAmount(value, metric) {
  if (metric) {
    if (value.compare(new Fraction(100)) >= 0) {
      // To the nearest 5, halves up.
      return String(floorFraction(value.mul(new Fraction(1, 5)).add(HALF)) * 5);
    }
    const tenths = floorFraction(value.mul(new Fraction(10)).add(HALF));
    return String(tenths / 10);
  }
  let whole = Math.trunc(value.n / value.d);
  const part = value.sub(new Fraction(whole));
  let nearest = NICE_FRACTIONS[0];
  for (const nice of NICE_FRACTIONS) {
    const distance = Math.abs(nice[0].sub(part).value());
    if (distance < Math.abs(nearest[0].sub(part).value())) nearest = nice;
  }
  if (nearest[0].compare(ONE) === 0) {
    whole += 1;
    nearest = NICE_FRACTIONS[0];
  }
  if (whole === 0 && nearest[0].n === 0) return "⅛";
  return `${whole || ""}${nearest[1]}`;
}

export function recipeFromData(id, data) {
  const servings = SERVING_CHOICES.includes(data.servings) ? data.servings : 2;
  return {
    id,
    title: String(data.title ?? ""),
    servings,
    tags: Array.isArray(data.tags) ? data.tags.map((tag) => cleanTag(String(tag))) : [],
    minutes: Number.isInteger(data.minutes) && data.minutes > 0 ? data.minutes : null,
    ingredients: (Array.isArray(data.ingredients) ? data.ingredients : [])
      .filter((item) => item && typeof item === "object")
      .map(Ingredient.fromData),
    steps: Array.isArray(data.steps) ? data.steps.map(String) : [],
    notes: String(data.notes ?? ""),
    favourite: Boolean(data.favourite),
    last_cooked: typeof data.last_cooked === "string" && /^\d{4}-\d{2}-\d{2}$/.test(data.last_cooked)
      ? data.last_cooked
      : null,
    created_at: String(data.created_at ?? ""),
  };
}

export function recipeData(recipe) {
  return {
    title: recipe.title,
    servings: recipe.servings,
    tags: recipe.tags,
    minutes: recipe.minutes,
    ingredients: recipe.ingredients.map((item) => item.toData()),
    steps: recipe.steps,
    notes: recipe.notes,
    favourite: recipe.favourite,
    last_cooked: recipe.last_cooked,
    created_at: recipe.created_at,
  };
}

export function factor(recipe, servings) {
  return new Fraction(servings, recipe.servings);
}

export function summary(recipe) {
  const parts = [...recipe.tags];
  if (recipe.minutes) parts.push(formatMinutes(recipe.minutes));
  return parts.join(" · ");
}

// Each typed word must start a word in the recipe: "spag" finds spaghetti,
// "eggs" finds "1 egg", but "egg" doesn't find "veggie".
export function matches(recipe, query) {
  query = query.trim().toLowerCase();
  if (!query) return true;
  const words = [recipe.title, ...recipe.tags, ...recipe.ingredients.map((item) => item.name)]
    .join(" ").toLowerCase().match(WORD) ?? [];
  return (query.match(WORD) ?? []).every((typed) =>
    words.some((word) => word.startsWith(typed) || word.startsWith(singularize(typed))),
  );
}

// Ingredients a step mentions, by name or by kind ("the pasta").
export function ingredientsForStep(recipe, step) {
  const text = step.toLowerCase();
  return recipe.ingredients.filter((item) => {
    const words = item.name.toLowerCase().match(/[a-z]+/g) ?? [];
    const named = words.some((word) => word.length > 3 && text.includes(word));
    const kind = Object.entries(INGREDIENT_KINDS).some(
      ([kindName, kinds]) => text.includes(kindName) && words.some((word) => kinds.some((k) => word.startsWith(k))),
    );
    return named || kind;
  });
}

export function formatDuration(seconds) {
  if (seconds < 60) return `${seconds} sec`;
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  const text = formatMinutes(minutes);
  return rest ? `${text} ${rest} sec` : text;
}

export function formatMinutes(minutes) {
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest ? `${hours} h ${rest} min` : `${hours} h`;
}

// Seconds for the first duration a step mentions; a range uses the shorter.
export function stepTimer(step) {
  const match = step.match(TIMER_PATTERN);
  if (!match) return null;
  const value = Number(match[1]);
  const unit = match[2].toLowerCase();
  const seconds = Math.round(unit.startsWith("h") ? value * 3600 : unit.startsWith("m") ? value * 60 : value);
  return seconds > 0 && seconds <= MAX_TIMER_SECONDS ? seconds : null;
}

export function cookedLabel(cooked, today) {
  if (!cooked) return "not cooked yet";
  const days = Math.round((Date.parse(today) - Date.parse(cooked)) / 86400000);
  if (days <= 0) return "cooked today";
  if (days === 1) return "cooked yesterday";
  if (days < 14) return `cooked ${days} days ago`;
  const date = new Date(`${cooked}T00:00:00`);
  return `cooked ${date.getDate()} ${date.toLocaleString("en-GB", { month: "short" })}`.toLowerCase();
}

export function cleanTag(tag) {
  return tag.trim().toLowerCase().split(/\s+/).filter(Boolean).join(" ");
}

export function parseTags(text) {
  const tags = [];
  for (const part of text.split(",")) {
    const tag = cleanTag(part);
    if (tag && !tags.includes(tag)) tags.push(tag);
  }
  return tags;
}

export function parseSteps(text) {
  return text.split(/\r?\n/).filter((line) => line.trim()).map((line) => line.replace(STEP_NUMBER, "").trim());
}

export function parseIngredients(text) {
  return text.split(/\r?\n/)
    .map((line) => line.replace(/^[-•* ]+/, "").trim())
    .filter(Boolean)
    .map(Ingredient.parse);
}

const DURATION_PATTERN = /^\s*(?:(\d+)\s*h(?:ours?|rs?)?)?\s*(?:(\d+)\s*(?:m|mins?|minutes?)?)?\s*$/i;

// "25", "1h 30" or "90 min" as minutes; null when empty.
export function parseMinutes(text) {
  if (!text.trim()) return null;
  const match = text.match(DURATION_PATTERN);
  if (!match || !(match[1] || match[2])) throw new Error("write the time like 25, 90 min or 1h 30");
  return Number(match[1] || 0) * 60 + Number(match[2] || 0) || null;
}

export function tagCounts(recipes) {
  const counts = new Map();
  for (const recipe of recipes) for (const tag of recipe.tags) counts.set(tag, (counts.get(tag) ?? 0) + 1);
  return [...counts.entries()].sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : 1));
}

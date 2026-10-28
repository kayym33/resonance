// Checks phone/js/recipes.js against resonance/recipes.py, the reference:
// the same ingredient lines, scalings, steps and searches must give the
// same answers. Run from the repo root: node phone/tests/parity.mjs
import { execFileSync } from "node:child_process";
import * as recipes from "../js/recipes.js";

const LINES = [
  "200g spaghetti", "200 g spaghetti", "2 eggs", "1 egg", "1 1/2 tbsp olive oil",
  "½ tsp salt", "1½ cups flour", "2-3 cloves garlic", "2 to 3 cloves garlic, crushed",
  "1 red onion, diced", "2 onions", "salt to taste", "3 tomatoes", "1 potato",
  "1 bunch parsley", "2 cans chopped tomatoes", "1 can coconut milk", "225g butter",
  "112.5 g sugar", "0.25 kg rice", "1.5 l stock", "50ml cream", "3 tbsp. soy sauce",
  "1 pinch chilli flakes", "4 slices bread", "1 cherry", "2 cherries", "1 dish",
  "1 box", "1 leaf", "2 berries", "1/3 cup milk", "5 g yeast", "1 lb mince",
  "7 oz chocolate", "1 handful spinach", "2 sprigs thyme", "1 stick celery",
  "1 piece ginger", "1 tin beans", "1 g", "3 large eggs", "¼ cabbage",
];
const FACTORS = [[1, 2], [2, 1], [1, 1], [1, 3], [2, 3], [3, 2]];
const STEPS = [
  "Boil the pasta in salted water for 10 minutes.", "Fry 4 minutes a side.",
  "Simmer for 10-12 mins.", "Bake 1 hr.", "Rest 30 secs.", "Season with salt.",
  "Whisk the eggs with the cheese.", "Scatter the herbs.", "Add the garlic and onion.",
  "Cook the noodles.", "Leave 1.5 hours", "wait 0 minutes",
];
const QUERIES = ["spag", "eggs", "egg", "veggie", "tomato", "garlic onion", "", "pasta italian", "xyz"];
const TEXTS = {
  tags: "Pasta, italian,  quick , pasta",
  steps: "1. Boil water\n2) Add pasta\n\n  3 . Drain",
  ingredients: "- 200g spaghetti\n• 2 eggs\n\n* salt to taste",
  minutes: ["25", "1h 30", "90 min", "2 hours", "", "1 h"],
};

const python = String.raw`
import json, sys
from fractions import Fraction
sys.path.insert(0, ".")
from resonance.recipes import (Ingredient, Recipe, parse_ingredients,
    parse_minutes, parse_steps, parse_tags, step_timer)
cases = json.load(sys.stdin)
out = {"lines": [], "steps": [], "queries": []}
for line in cases["lines"]:
    item = Ingredient.parse(line)
    out["lines"].append({"data": item.to_data(),
        "formats": [item.format(Fraction(a, b)) for a, b in cases["factors"]]})
recipe = Recipe("Spaghetti Carbonara", 2, ["pasta", "italian"], 25,
    [Ingredient.parse(line) for line in cases["lines"]], [])
for step in cases["steps"]:
    out["steps"].append({"timer": step_timer(step),
        "needs": [item.name for item in recipe.ingredients_for_step(step)]})
out["queries"] = [recipe.matches(query) for query in cases["queries"]]
texts = cases["texts"]
out["tags"] = parse_tags(texts["tags"])
out["parsed_steps"] = parse_steps(texts["steps"])
out["parsed_ingredients"] = [item.to_data() for item in parse_ingredients(texts["ingredients"])]
out["minutes"] = [parse_minutes(text) for text in texts["minutes"]]
print(json.dumps(out))
`;

const cases = { lines: LINES, factors: FACTORS, steps: STEPS, queries: QUERIES, texts: TEXTS };
const expected = JSON.parse(
  execFileSync(process.env.PYTHON ?? "python3", ["-c", python], { input: JSON.stringify(cases) }),
);

const actual = { lines: [], steps: [], queries: [] };
for (const line of LINES) {
  const item = recipes.Ingredient.parse(line);
  actual.lines.push({
    data: item.toData(),
    formats: FACTORS.map(([a, b]) => item.format(new recipes.Fraction(a, b))),
  });
}
const recipe = {
  title: "Spaghetti Carbonara", servings: 2, tags: ["pasta", "italian"], minutes: 25,
  ingredients: LINES.map((line) => recipes.Ingredient.parse(line)), steps: [],
};
for (const step of STEPS) {
  actual.steps.push({
    timer: recipes.stepTimer(step),
    needs: recipes.ingredientsForStep(recipe, step).map((item) => item.name),
  });
}
actual.queries = QUERIES.map((query) => recipes.matches(recipe, query));
actual.tags = recipes.parseTags(TEXTS.tags);
actual.parsed_steps = recipes.parseSteps(TEXTS.steps);
actual.parsed_ingredients = recipes.parseIngredients(TEXTS.ingredients).map((item) => item.toData());
actual.minutes = TEXTS.minutes.map((text) => recipes.parseMinutes(text));

let failures = 0;
function compare(path, want, got) {
  if (JSON.stringify(want) !== JSON.stringify(got)) {
    failures += 1;
    console.log(`FAIL ${path}\n  python: ${JSON.stringify(want)}\n  js:     ${JSON.stringify(got)}`);
  }
}
expected.lines.forEach((want, index) => compare(`line ${JSON.stringify(LINES[index])}`, want, actual.lines[index]));
expected.steps.forEach((want, index) => compare(`step ${JSON.stringify(STEPS[index])}`, want, actual.steps[index]));
expected.queries.forEach((want, index) => compare(`query ${JSON.stringify(QUERIES[index])}`, want, actual.queries[index]));
for (const key of ["tags", "parsed_steps", "parsed_ingredients", "minutes"]) compare(key, expected[key], actual[key]);

const total = LINES.length + STEPS.length + QUERIES.length + 4;
console.log(failures ? `${failures} of ${total} differ` : `all ${total} match`);
process.exit(failures ? 1 : 0);

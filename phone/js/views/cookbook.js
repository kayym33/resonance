// Cookbook: search and tags, one recipe scaled for one or two, cooking
// mode (one step at a time, with timers) and the editor. The recipe logic
// is in recipes.js, a port of the desktop's recipes.py.
import {
  cookedLabel, CUISINES, factor, formatDuration, formatMinutes, ingredientsForStep, matches,
  parseIngredients, parseMinutes, parseSteps, parseTags, SERVING_CHOICES, stepTimer, summary, tagCounts,
} from "../recipes.js";
import { nowIso } from "../store.js";
import { action, button, esc, heading, picker, today, uuid } from "../ui.js";

// The view's own state, kept while you move around the app.
const state = { query: "", tags: new Set(), servings: 2, step: 0, wakeLock: null };

function recipeRows(recipes, detail = summary) {
  return `<ul class="recipes">${recipes.map((recipe) => `
    <li ${action("go", { to: `/cook/${recipe.id}` })}>
      <strong>${recipe.favourite ? "★ " : ""}${esc(recipe.title)}</strong>
      <span class="muted">${esc(detail(recipe))}</span>
    </li>`).join("")}</ul>`;
}

function filtered(recipes) {
  return recipes.filter((recipe) => matches(recipe, state.query) && [...state.tags].every((tag) => recipe.tags.includes(tag)));
}

function chips(recipes) {
  const counts = tagCounts(recipes);
  const group = (title, list) => (list.length
    ? `<h3>${esc(title)}</h3><div class="chips">${list.map(([tag, count]) => `
        <button type="button" class="chip${state.tags.has(tag) ? " on" : ""}" ${action("cook-tag", { tag })}>${esc(tag)} ${count}</button>`).join("")}</div>`
    : "");
  return group("dishes", counts.filter(([tag]) => !CUISINES.has(tag)))
    + group("cuisines", counts.filter(([tag]) => CUISINES.has(tag)));
}

export function renderHome(ctx) {
  const recipes = ctx.data.recipes();
  if (!recipes.length) {
    return {
      crumbs: ["cookbook"],
      html: `
        <div class="row-buttons"><span class="spacer"></span>${button("+ new recipe", "go", { to: "/cook/new/edit" }, { solid: true })}</div>
        <pre class="art center">    ~   ~   ~    \n  .-----------.  \n =|           |= \n  '-----------'  </pre>
        <p class="muted center">no recipes yet</p>`,
    };
  }
  const browsing = state.query || state.tags.size;
  const favourites = recipes.filter((recipe) => recipe.favourite);
  const cooked = recipes.filter((recipe) => recipe.last_cooked)
    .sort((a, b) => b.last_cooked.localeCompare(a.last_cooked)).slice(0, 5);
  const day = today();
  return {
    crumbs: ["cookbook"],
    html: `
      <div class="row-buttons">
        <span class="muted">${recipes.length} recipe${recipes.length === 1 ? "" : "s"}</span>
        <span class="spacer"></span>
        ${button("+ new recipe", "go", { to: "/cook/new/edit" }, { solid: true })}
      </div>
      <input class="search" type="search" placeholder="search recipes, tags or ingredients"
        value="${esc(state.query)}" data-input="cook-search" autocomplete="off" enterkeyhint="search">
      <div data-part="cook-results">${results(recipes, browsing, favourites, cooked, day)}</div>
      ${chips(recipes)}`,
  };
}

function results(recipes, browsing, favourites, cooked, day) {
  if (browsing) {
    const found = filtered(recipes);
    return `${heading(`${found.length} found`)}${found.length ? recipeRows(found) : `<p class="muted">nothing matches</p>`}`;
  }
  return [
    favourites.length ? `${heading("favourites")}${recipeRows(favourites)}` : "",
    cooked.length ? `${heading("recently cooked")}${recipeRows(cooked, (recipe) => cookedLabel(recipe.last_cooked, day))}` : "",
    `${heading("all recipes")}${recipeRows(recipes)}`,
  ].join("");
}

export function renderRecipe(ctx, { id }) {
  const recipe = ctx.data.recipe(id);
  if (!recipe) return { crumbs: ["cookbook", "gone"], html: `<p class="muted">that recipe was deleted</p>` };
  const scale = factor(recipe, state.servings);
  const scaled = scale.n !== scale.d;
  return {
    crumbs: [["cookbook", "/cook"], recipe.title],
    html: `
      <div class="recipe-head">
        <h1>${esc(recipe.title)} <button type="button" class="star${recipe.favourite ? " on" : ""}" ${action("cook-favourite", { id })} aria-label="favourite">${recipe.favourite ? "★" : "☆"}</button></h1>
        ${picker("for", SERVING_CHOICES, state.servings, "cook-servings")}
      </div>
      <p class="muted">${esc([summary(recipe), cookedLabel(recipe.last_cooked, today())].filter(Boolean).join("  ·  "))}</p>
      <div class="row-buttons">
        ${recipe.steps.length ? button("cook ->", "cook-start", { id }, { solid: true }) : ""}
        ${button("edit", "go", { to: `/cook/${id}/edit` })}
        ${recipe.ingredients.length ? button("+ shopping to-do", "cook-shopping", { id }) : ""}
      </div>
      ${heading("ingredients")}
      ${scaled ? `<p class="hint">scaled from ${recipe.servings}</p>` : ""}
      <ul class="ingredients">${recipe.ingredients.map((item) => `<li>${esc(item.format(scale))}</li>`).join("") || `<li class="muted">none listed</li>`}</ul>
      ${heading("steps")}
      <ol class="steps">${recipe.steps.map((step) => `<li>${esc(step)}</li>`).join("") || `<li class="muted">no steps yet</li>`}</ol>
      ${recipe.notes ? `${heading("notes")}<p class="notes">${esc(recipe.notes)}</p>` : ""}`,
  };
}

export function renderCooking(ctx, { id }) {
  const recipe = ctx.data.recipe(id);
  if (!recipe || !recipe.steps.length) return renderRecipe(ctx, { id });
  state.step = Math.max(0, Math.min(state.step, recipe.steps.length - 1));
  const step = recipe.steps[state.step];
  const last = state.step === recipe.steps.length - 1;
  const scale = factor(recipe, state.servings);
  const needed = ingredientsForStep(recipe, step);
  const seconds = stepTimer(step);
  const dots = recipe.steps.map((_, index) => (index <= state.step ? "■" : "□")).join(" ");
  let timer = "";
  if (seconds) {
    timer = ctx.timers.running(recipe.id, state.step + 1)
      ? `<p class="muted">timer running ^</p>`
      : button(`start ${formatDuration(seconds)} timer`, "cook-timer", { id, seconds });
  }
  return {
    crumbs: [["cookbook", "/cook"], [recipe.title, `/cook/${id}`], "cooking"],
    className: "cooking",
    html: `
      <div class="recipe-head">
        <span class="label">step ${state.step + 1} of ${recipe.steps.length}  <span class="dots">${dots}</span></span>
        ${picker("for", SERVING_CHOICES, state.servings, "cook-servings")}
      </div>
      <p class="step" data-swipe="cook-step">${esc(step)}</p>
      ${needed.length ? `${heading("you'll need")}<ul class="ingredients">${needed.map((item) => `<li>${esc(item.format(scale))}</li>`).join("")}</ul>` : ""}
      <div class="timer-row">${timer}</div>
      <div class="next">${last ? `<p class="hint">last step</p>` : `${heading("next")}<p class="faded">${esc(recipe.steps[state.step + 1])}</p>`}</div>
      <div class="row-buttons bottom">
        <span class="hint">swipe or tap</span>
        <span class="spacer"></span>
        ${state.step > 0 ? button("<- back", "cook-step", { by: -1 }) : ""}
        ${last ? button("done ~", "cook-finish", { id }, { solid: true }) : button("next ->", "cook-step", { by: 1 }, { solid: true })}
      </div>`,
  };
}

export function renderEditor(ctx, { id }) {
  const isNew = id === "new";
  const recipe = isNew ? null : ctx.data.recipe(id);
  if (!isNew && !recipe) return { crumbs: ["cookbook", "gone"], html: `<p class="muted">that recipe was deleted</p>` };
  const value = (text) => esc(text ?? "");
  return {
    crumbs: [["cookbook", "/cook"], ...(recipe ? [[recipe.title, `/cook/${id}`]] : []), isNew ? "new recipe" : "edit"],
    html: `
      <form class="editor" data-form="cook-save" data-id="${esc(isNew ? uuid() : id)}" data-new="${isNew}">
        <label>title<input name="title" value="${value(recipe?.title)}" required autocomplete="off"></label>
        <div class="pair">
          <label>serves<select name="servings">${SERVING_CHOICES.map((choice) => `<option${choice === (recipe?.servings ?? 2) ? " selected" : ""}>${choice}</option>`).join("")}</select></label>
          <label>time<input name="minutes" value="${value(recipe?.minutes ? formatMinutes(recipe.minutes) : "")}" placeholder="25, 1h 30" autocomplete="off"></label>
        </div>
        <label>tags<input name="tags" value="${value(recipe?.tags.join(", "))}" placeholder="pasta, italian, quick" autocomplete="off"></label>
        <label>ingredients<span class="hint">one per line, like 200g spaghetti</span>
          <textarea name="ingredients" rows="7">${value(recipe?.ingredients.map((item) => item.format()).join("\n"))}</textarea></label>
        <label>steps<span class="hint">one per line; times like "10 minutes" get a timer</span>
          <textarea name="steps" rows="8">${value(recipe?.steps.join("\n"))}</textarea></label>
        <label>notes<textarea name="notes" rows="3">${value(recipe?.notes)}</textarea></label>
        <p class="error" hidden></p>
        <div class="row-buttons">
          <button type="submit" class="button solid">save</button>
          ${button("cancel", "go", { to: isNew ? "/cook" : `/cook/${id}` })}
          <span class="spacer"></span>
          ${isNew ? "" : button("delete", "cook-delete", { id })}
        </div>
      </form>`,
  };
}

async function keepAwake(on) {
  // Keeps the screen on while cooking, where the browser allows it.
  try {
    if (on && !state.wakeLock && navigator.wakeLock) state.wakeLock = await navigator.wakeLock.request("screen");
    if (!on && state.wakeLock) {
      await state.wakeLock.release();
      state.wakeLock = null;
    }
  } catch {
    state.wakeLock = null;
  }
}

const RECIPE_ROUTES = new Set(["recipe", "cooking", "recipe-edit"]);

export function onRoute(route, previous) {
  keepAwake(route.name === "cooking");
  // Coming back from a recipe keeps the search; arriving from another
  // tab starts a fresh one.
  if (route.name === "cookbook" && !RECIPE_ROUTES.has(previous)) {
    state.query = "";
    state.tags.clear();
  }
}

export const actions = {
  "cook-tag"(ctx, { tag }) {
    if (state.tags.has(tag)) state.tags.delete(tag);
    else state.tags.add(tag);
    ctx.render();
  },
  "cook-servings"(ctx, { value }) {
    state.servings = Number(value);
    ctx.render();
  },
  "cook-favourite"(ctx, { id }) {
    const recipe = ctx.data.recipe(id);
    if (recipe) ctx.data.saveRecipe({ ...recipe, favourite: !recipe.favourite });
  },
  "cook-start"(ctx, { id }) {
    state.step = 0;
    ctx.go(`/cook/${id}/cooking`);
  },
  "cook-step"(ctx, { by }) {
    state.step += Number(by);
    ctx.render();
  },
  "cook-timer"(ctx, { id, seconds }) {
    const recipe = ctx.data.recipe(id);
    if (!recipe) return;
    ctx.timers.start(recipe, state.step + 1, recipe.steps[state.step], Number(seconds));
    ctx.render();
  },
  "cook-finish"(ctx, { id }) {
    const recipe = ctx.data.recipe(id);
    if (!recipe) return;
    ctx.data.saveRecipe({ ...recipe, last_cooked: today() });
    ctx.flash("nice ~ marked as cooked today");
    ctx.go(`/cook/${id}`);
  },
  "cook-shopping"(ctx, { id }) {
    const recipe = ctx.data.recipe(id);
    if (!recipe) return;
    const scale = factor(recipe, state.servings);
    ctx.data.addTask(`shop for ${recipe.title.toLowerCase()}: ${recipe.ingredients.map((item) => item.format(scale)).join(", ")}`);
    ctx.flash("added a shopping list to your to-dos");
  },
  "cook-delete"(ctx, { id }) {
    if (!confirm("delete this recipe?")) return;
    ctx.data.deleteRecipe(id);
    ctx.go("/cook");
  },
};

export const inputs = {
  "cook-search"(ctx, input) {
    state.query = input.value;
    // Only the results change, so the search box keeps focus.
    const recipes = ctx.data.recipes();
    const favourites = recipes.filter((recipe) => recipe.favourite);
    const cooked = recipes.filter((recipe) => recipe.last_cooked)
      .sort((a, b) => b.last_cooked.localeCompare(a.last_cooked)).slice(0, 5);
    document.querySelector('[data-part="cook-results"]').innerHTML = results(
      recipes, state.query || state.tags.size, favourites, cooked, today(),
    );
  },
};

export const swipes = {
  "cook-step"(ctx, direction) {
    state.step += direction;
    ctx.render();
  },
};

export const forms = {
  "cook-save"(ctx, form) {
    const fields = form.elements;
    const error = form.querySelector(".error");
    let minutes;
    try {
      minutes = parseMinutes(fields.minutes.value);
    } catch (problem) {
      error.textContent = problem.message;
      error.hidden = false;
      return;
    }
    const title = fields.title.value.trim();
    if (!title) {
      error.textContent = "give it a title";
      error.hidden = false;
      return;
    }
    const existing = form.dataset.new === "true" ? null : ctx.data.recipe(form.dataset.id);
    ctx.data.saveRecipe({
      id: form.dataset.id,
      title,
      servings: Number(fields.servings.value),
      tags: parseTags(fields.tags.value),
      minutes,
      ingredients: parseIngredients(fields.ingredients.value),
      steps: parseSteps(fields.steps.value),
      notes: fields.notes.value.trim(),
      favourite: existing?.favourite ?? false,
      last_cooked: existing?.last_cooked ?? null,
      created_at: existing?.created_at ?? nowIso(),
    });
    ctx.go(`/cook/${form.dataset.id}`);
  },
};

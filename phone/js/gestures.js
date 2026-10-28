// Touch gestures that make the web app feel like an iPhone app: swiping
// back from the left edge, swiping a row to tick or delete it, swiping
// between cooking steps, and pulling down to sync. Each follows the finger, then settles with an animation.
//
// A touch is claimed by the first gesture whose direction it moves in, so
// they never fight each other or the page's normal scrolling.

// How far a touch moves before its direction is decided.
const SLOP = 10;
import { haptic } from "./ui.js";

// Edge swipes start this close to the left of the screen.
const EDGE = 24;
// Past this share of the screen (or a quick flick), a swipe back happens.
const BACK_SHARE = 0.33;
// A row acts once swiped past this share of its width.
const ROW_SHARE = 0.35;
// How far to pull before letting go syncs.
const PULL_DISTANCE = 64;
const SETTLE_MS = 220;

const reducedMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

function settle(element, transform, then) {
  if (reducedMotion()) {
    element.style.transform = transform;
    then?.();
    return;
  }
  element.style.transition = `transform ${SETTLE_MS}ms cubic-bezier(0.2, 0.8, 0.2, 1)`;
  element.style.transform = transform;
  let finished = false;
  const done = () => {
    if (finished) return;
    finished = true;
    element.style.transition = "";
    then?.();
  };
  element.addEventListener("transitionend", done, { once: true });
  // No transitionend comes if it was already there, or was replaced.
  setTimeout(done, SETTLE_MS + 60);
}

// options: main (the page element), standalone() (true in the home-screen
// app, where iOS gives no back swipe of its own), parent() (where back goes,
// or null), onBack(path), onRowAction(name, dataset), swipeArea() (an
// element swiped as a whole, like cooking mode's step, or null),
// onSwipe(name, direction), onPull(), and pulling() (true while a pull's
// sync is still running).
export function installGestures(options) {
  const { main } = options;
  const pull = document.querySelector(".pull");
  let touch = null;

  document.addEventListener("touchstart", (event) => {
    if (event.touches.length !== 1) {
      touch = null;
      return;
    }
    const point = event.touches[0];
    touch = {
      x: point.clientX,
      y: point.clientY,
      time: event.timeStamp,
      kind: null,
      row: event.target.closest("[data-swipe-left], [data-swipe-right]"),
      area: event.target.closest("[data-swipe]") ?? options.swipeArea(),
      edge: point.clientX < EDGE && options.standalone() && options.parent() !== null,
      top: window.scrollY <= 0 && !event.target.closest("input, textarea, select"),
    };
  }, { passive: true });

  document.addEventListener("touchmove", (event) => {
    if (!touch) return;
    const point = event.touches[0];
    const dx = point.clientX - touch.x;
    const dy = point.clientY - touch.y;
    if (!touch.kind) {
      if (Math.abs(dx) < SLOP && Math.abs(dy) < SLOP) return;
      const sideways = Math.abs(dx) > Math.abs(dy);
      if (sideways && touch.edge && dx > 0) touch.kind = "back";
      else if (sideways && touch.row) touch.kind = "row";
      else if (sideways && touch.area) touch.kind = "swipe";
      else if (!sideways && dy > 0 && touch.top && !options.pulling()) touch.kind = "pull";
      else touch.kind = "scroll";
    }
    if (touch.kind === "scroll") return;
    // The gesture owns this touch now, so the page mustn't scroll too.
    event.preventDefault();
    if (touch.kind === "back") {
      main.style.transform = `translateX(${Math.max(0, dx)}px)`;
      main.classList.add("dragging");
    } else if (touch.kind === "row") {
      moveRow(touch.row, dx);
    } else if (touch.kind === "swipe") {
      // A little give, so it's clear the step can be swiped.
      touch.area.style.transform = `translateX(${dx * 0.25}px)`;
    } else if (touch.kind === "pull") {
      // Resists like a spring: the further, the harder.
      const distance = Math.min(PULL_DISTANCE * 1.6, dy * 0.5);
      touch.pulled = distance;
      pull.style.height = `${distance}px`;
      pull.textContent = distance >= PULL_DISTANCE ? "release to sync" : "pull to sync";
    }
  }, { passive: false });

  const finish = (event) => {
    if (!touch || !touch.kind || touch.kind === "scroll") {
      touch = null;
      return;
    }
    const point = event.changedTouches[0];
    const dx = point.clientX - touch.x;
    // A quick flick counts even if it's short.
    const fast = Math.abs(dx) / Math.max(1, event.timeStamp - touch.time) > 0.5;
    const { kind, row, area, pulled } = touch;
    touch = null;
    if (event.type === "touchcancel") {
      if (kind === "back") settle(main, "translateX(0)", () => main.classList.remove("dragging"));
      if (kind === "row") releaseRow(row, 0, options);
      if (kind === "swipe") settle(area, "translateX(0)");
      if (kind === "pull") collapsePull(pull);
      return;
    }
    if (kind === "back") {
      const parent = options.parent();
      if (parent !== null && (dx > window.innerWidth * BACK_SHARE || (fast && dx > 40))) {
        haptic();
        settle(main, `translateX(${window.innerWidth}px)`, () => {
          main.classList.remove("dragging");
          main.style.transform = "";
          options.onBack(parent);
        });
      } else {
        settle(main, "translateX(0)", () => main.classList.remove("dragging"));
      }
    } else if (kind === "row") {
      releaseRow(row, dx, options);
    } else if (kind === "swipe") {
      settle(area, "translateX(0)");
      if (Math.abs(dx) > 60 || (fast && Math.abs(dx) > 30)) {
        haptic();
        options.onSwipe(area.dataset.swipe, dx < 0 ? 1 : -1);
      }
    } else if (kind === "pull") {
      if (pulled >= PULL_DISTANCE) {
        haptic();
        pull.style.transition = `height ${SETTLE_MS}ms`;
        pull.style.height = "36px";
        pull.textContent = "~ syncing";
        options.onPull();
      } else {
        collapsePull(pull);
      }
    }
  };
  document.addEventListener("touchend", finish);
  document.addEventListener("touchcancel", finish);

  return {
    // Called when the pull's sync is over.
    pullDone() {
      if (pull.textContent === "~ syncing") collapsePull(pull);
    },
  };
}

function collapsePull(pull) {
  pull.style.transition = `height ${SETTLE_MS}ms`;
  pull.style.height = "0px";
  setTimeout(() => {
    pull.style.transition = "";
    pull.textContent = "";
  }, SETTLE_MS);
}

// Rows: the content slides, and what letting go would do shows behind it.
function moveRow(row, dx) {
  const slide = row.querySelector(".slide");
  const side = dx > 0 ? "right" : "left";
  if (!row.dataset[side === "right" ? "swipeRight" : "swipeLeft"]) dx = 0;
  row.dataset.showing = dx === 0 ? "" : side;
  row.dataset.armed = Math.abs(dx) > row.offsetWidth * ROW_SHARE ? "yes" : "";
  slide.style.transform = `translateX(${dx}px)`;
}

function releaseRow(row, dx, options) {
  const slide = row.querySelector(".slide");
  const side = dx > 0 ? "swipeRight" : "swipeLeft";
  const name = row.dataset[side];
  const reset = () => {
    row.dataset.showing = "";
    row.dataset.armed = "";
  };
  if (!name || Math.abs(dx) <= row.offsetWidth * ROW_SHARE) {
    settle(slide, "translateX(0)", reset);
    return;
  }
  // Now, while the finger is lifting: iOS only allows it during a touch.
  haptic();
  if (side === "swipeLeft") {
    // Deleting: slide away, fold the row up, then delete it.
    settle(slide, `translateX(${-row.offsetWidth}px)`, () => {
      row.style.height = `${row.offsetHeight}px`;
      row.classList.add("folding");
      requestAnimationFrame(() => {
        row.style.height = "0px";
      });
      setTimeout(() => options.onRowAction(name, { ...row.dataset }), reducedMotion() ? 0 : SETTLE_MS);
    });
  } else {
    settle(slide, "translateX(0)", () => {
      reset();
      options.onRowAction(name, { ...row.dataset });
    });
  }
}

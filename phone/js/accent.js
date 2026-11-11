// The accent colour, the same presets as resonance/accent.py (the desktop
// tests check they agree). The app stays bone and ink; the accent colours
// focus outlines, swipe-to-delete, stars, the "now" dot and flashes, and a
// share of the noise at the top ("specks"). Errors keep their orange-red.
// A flag's stripes go to the specks; one of its colours to everything else.

// name: {mark: [day, night], text: [day, night], stripes: [top to bottom]}
export const PRESETS = {
  orange: { mark: ["#E8642C", "#E8642C"], text: ["#B44718", "#F08A5D"] },
  ochre: { mark: ["#C08A1E", "#D6A23A"], text: ["#7C5806", "#DDB04F"] },
  moss: { mark: ["#6B8A3A", "#86A852"], text: ["#4A6324", "#A3C27A"] },
  slate: { mark: ["#4F6F8F", "#7193B4"], text: ["#3A5878", "#8FAECB"] },
  plum: { mark: ["#8A4F7D", "#B07AA3"], text: ["#6E3A63", "#C493B8"] },
  rose: { mark: ["#C7647A", "#D97F92"], text: ["#9B3E54", "#E596A8"] },
  trans: {
    mark: ["#5A93AF", "#86BCD4"], text: ["#386C86", "#8EC3DA"],
    stripes: ["#7FB3CC", "#DDA5B1", "#F2EFE8", "#DDA5B1", "#7FB3CC"],
  },
  lesbian: {
    mark: ["#C24F8C", "#DC7DB0"], text: ["#9A2F69", "#E59AC2"],
    stripes: ["#B4532F", "#CC8150", "#DDA57A", "#F2EFE8", "#D46FA6", "#BA5292", "#962E66"],
  },
};
export const DEFAULT = "orange";
// Higher than the desktop's: the phone's noise is short and small.
export const SPECK_SHARE = 0.4;
// White stripes vanish on bone, so the day theme uses this grey.
const DAY_WHITE = "#9A9B90";
const WHITES = new Set(["#FFFFFF", "#F2EFE8"]);

export function preset(name) {
  return PRESETS[name] ?? PRESETS[DEFAULT];
}

export function speckColors(name, night) {
  const chosen = preset(name);
  if (!chosen.stripes) return [chosen.mark[night ? 1 : 0]];
  return chosen.stripes.map((stripe) => (WHITES.has(stripe) && !night ? DAY_WHITE : stripe));
}

// A small square for pickers: the flag's stripes, or the colour.
export function swatch(name) {
  const chosen = preset(name);
  return chosen.stripes ? bands(chosen.stripes, "to bottom") : chosen.mark[0];
}

// Sets the CSS colours for the accent in the current theme.
export function applyAccent(name, night) {
  const chosen = preset(name);
  const root = document.documentElement.style;
  root.setProperty("--accent", chosen.mark[night ? 1 : 0]);
  root.setProperty("--accent-text", chosen.text[night ? 1 : 0]);
  root.setProperty("--accent-bar", chosen.stripes ? bands(chosen.stripes, "to right") : chosen.mark[night ? 1 : 0]);
}

function bands(stripes, direction) {
  const step = 100 / stripes.length;
  return `linear-gradient(${direction}, ${stripes.map((stripe, index) => `${stripe} ${index * step}% ${(index + 1) * step}%`).join(", ")})`;
}

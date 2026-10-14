from __future__ import annotations

import math
import random
from typing import Any, Callable

from PIL import Image, ImageDraw, ImageFont, ImageOps

from .constants import (
    ALBUM_ART_SIZE,
    BACKGROUND,
    FIGURE_COLOR,
    FIGURE_SHADE,
    INK,
    MUTED,
)
from .theme import pick

# Lightest to darkest; a leading space lets highlights fall away to paper.
NIGHT_GAMMA = 1.8
NIGHT_DENSITY_CAP = 0.7
GLYPH_RAMP = " .`:-~=+*xo#%@"
NOISE_MARKS = ".,`'-:;~+*"
DEFAULT_NOISE_DENSITY = 0.42
FONT_FILES = (
    "DejaVuSansMono.ttf",
    "consola.ttf",
    "LiberationMono-Regular.ttf",
    "Menlo.ttc",
)

# A small figure drawn as blocky pixels on top of the noise.
FIGURE = (
    "..oo..",
    "..oo..",
    ".OooO.",
    "o.oo.o",
    "..oo..",
    ".o..o.",
    ".o..o.",
)


def load_glyph_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for font_file in FONT_FILES:
        try:
            return ImageFont.truetype(font_file, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def hex_to_rgb(color: str) -> tuple[int, int, int]:
    return (
        int(color[1:3], 16),
        int(color[3:5], 16),
        int(color[5:7], 16),
    )


def blend_rgb(
    start: tuple[int, int, int],
    end: tuple[int, int, int],
    amount: float,
) -> tuple[int, int, int]:
    return (
        round(start[0] + (end[0] - start[0]) * amount),
        round(start[1] + (end[1] - start[1]) * amount),
        round(start[2] + (end[2] - start[2]) * amount),
    )


def landscape(columns: int, rows: int, seed: int) -> Image.Image:
    """Grey hills and sky used when there is no album art to show."""
    rng = random.Random(seed)
    phase = rng.uniform(0, math.tau)
    image = Image.new("L", (columns, rows))
    pixels = []
    for y in range(rows):
        for x in range(columns):
            u = x / columns
            ridge = 0.55 + 0.12 * math.sin(u * 5 + phase) + 0.06 * math.sin(
                u * 13 + phase * 2
            )
            v = y / rows
            if v < ridge:
                pixels.append(round(255 * (0.75 + 0.25 * v / ridge)))
            else:
                pixels.append(round(255 * max(0.0, 0.32 - 0.6 * (v - ridge))))
    image.putdata(pixels)
    return image


def draw_figure(
    canvas: Image.Image,
    left: int,
    bottom: int,
    pixel: int,
    night: bool = False,
) -> None:
    rows = FIGURE
    draw = ImageDraw.Draw(canvas)
    top = bottom - len(rows) * pixel
    width = len(rows[0]) * pixel
    # Clear a little paper around the figure so it reads against dense noise.
    draw.rectangle(
        (left - pixel, top - pixel, left + width + pixel, bottom + pixel),
        fill=pick(BACKGROUND, night),
    )
    for row_index, row in enumerate(rows):
        for column_index, cell in enumerate(row):
            if cell == ".":
                continue
            x = left + column_index * pixel
            y = top + row_index * pixel
            draw.rectangle(
                (x, y, x + pixel - 1, y + pixel - 1),
                fill=FIGURE_SHADE if cell == "O" else FIGURE_COLOR,
            )


def render_ascii_art(
    source: Image.Image | None,
    size: int = ALBUM_ART_SIZE * 2,
    seed: int | str | None = None,
    cell: tuple[int, int] = (5, 8),
    figure: bool = True,
    night: bool = False,
    photo: bool = True,
) -> Image.Image:
    """Redraw an image as dithered glyph noise on bone paper.

    ``cell`` is the pixel size of one glyph; ``figure`` adds the little
    orange figure standing in the scene. At ``night`` the glyphs are
    light on dark paper, and a ``photo`` maps brightness (not darkness)
    to dense glyphs so it doesn't come out as a negative.
    """
    rng = random.Random(seed)
    cell_width, cell_height = cell
    columns, rows = size // cell_width, size // cell_height
    if source is None:
        tones = landscape(columns, rows, rng.randrange(1 << 30))
    else:
        tones = ImageOps.autocontrast(
            ImageOps.fit(source.convert("L"), (columns, rows)),
            cutoff=2,
        )

    positive = night and photo and source is not None
    canvas = Image.new("RGB", (size, size), pick(BACKGROUND, night))
    draw = ImageDraw.Draw(canvas)
    font = load_glyph_font(cell_height + 1)
    ink = hex_to_rgb(pick(INK, night))
    muted = hex_to_rgb(pick(MUTED, night))
    last_glyph = len(GLYPH_RAMP) - 1
    for y in range(rows):
        for x in range(columns):
            darkness = tones.getpixel((x, y)) / 255
            if positive:
                # Light glyphs on dark paper read much heavier than ink on
                # bone, so keep night art sparse: ease off the mid-tones and
                # never use the very densest glyphs.
                darkness = darkness ** NIGHT_GAMMA * NIGHT_DENSITY_CAP
            else:
                darkness = 1 - darkness
            darkness += rng.uniform(-0.12, 0.12)
            # Dissolve the edges into scattered marks.
            dx = (x + 0.5) / columns * 2 - 1
            dy = (y + 0.5) / rows * 2 - 1
            edge = max(abs(dx), abs(dy))
            if edge > 0.78 and rng.random() < (edge - 0.78) * 4:
                darkness *= rng.uniform(0, 0.5)
            index = max(0, min(last_glyph, round(darkness * last_glyph)))
            glyph = GLYPH_RAMP[index]
            if glyph == " ":
                continue
            color = blend_rgb(muted, ink, index / last_glyph)
            draw.text(
                (x * cell_width, y * cell_height - 1),
                glyph,
                font=font,
                fill=color,
            )

    if figure:
        draw_figure(
            canvas,
            left=round(size * 0.18),
            bottom=round(size * 0.86),
            pixel=max(2, size // 60),
            night=night,
        )
    return canvas


def initial_portrait(initial: str, size: int = 96) -> Image.Image:
    """A greyscale card with one big letter, for people without a picture."""
    image = Image.new("L", (size, size), 255)
    draw = ImageDraw.Draw(image)
    font = load_glyph_font(round(size * 0.8))
    draw.text(
        (size / 2, size / 2),
        (initial or "~")[0].lower(),
        font=font,
        fill=0,
        anchor="mm",
    )
    return image


def render_avatar(
    source: Image.Image | None,
    initial: str,
    size: int = 192,
    night: bool = False,
) -> Image.Image:
    """A profile picture in the same dithered style, without the figure."""
    portrait = source if source is not None else initial_portrait(initial)
    return render_ascii_art(
        portrait,
        size=size,
        seed=initial,
        cell=(4, 6),
        figure=False,
        night=night,
        photo=source is not None,
    )


def noise_char(rng: random.Random, density: float) -> str:
    return rng.choice(NOISE_MARKS) if rng.random() < density else " "


def noise_line(
    length: int,
    rng: random.Random | None = None,
    density: float = DEFAULT_NOISE_DENSITY,
) -> str:
    """``density`` is the share of positions holding a mark."""
    rng = rng or random.Random()
    return "".join(noise_char(rng, density) for _ in range(length))


def drift_noise(
    line: str,
    amount: float,
    rng: random.Random,
    density: float = DEFAULT_NOISE_DENSITY,
) -> str:
    """Flicker a fraction of the characters, like a weak terminal signal."""
    characters = list(line)
    for _ in range(max(1, round(len(characters) * amount))):
        characters[rng.randrange(len(characters))] = noise_char(rng, density)
    return "".join(characters)


# Ordered-dither thresholds for a 4x4 tile, scaled to 0-255.
BAYER_4 = (
    (0, 8, 2, 10),
    (12, 4, 14, 6),
    (3, 11, 1, 9),
    (15, 7, 13, 5),
)


def render_avatar_icon(
    source: Image.Image | None,
    initial: str,
    grid: int = 14,
    pixel: int = 4,
    night: bool = False,
) -> Image.Image:
    """A tiny pixel-art version for places too small for glyphs."""
    portrait = source if source is not None else initial_portrait(initial)
    if night and source is not None:
        # Light up the bright parts of a photo, as in render_ascii_art.
        portrait = ImageOps.invert(portrait.convert("L"))
    tones = ImageOps.autocontrast(
        ImageOps.fit(portrait.convert("L"), (grid, grid)),
        cutoff=2,
    )
    icon = Image.new("RGB", (grid * pixel, grid * pixel), pick(BACKGROUND, night))
    draw = ImageDraw.Draw(icon)
    for y in range(grid):
        for x in range(grid):
            threshold = (BAYER_4[y % 4][x % 4] + 0.5) * 16
            if tones.getpixel((x, y)) < threshold:
                draw.rectangle(
                    (x * pixel, y * pixel, (x + 1) * pixel - 1, (y + 1) * pixel - 1),
                    fill=pick(INK, night),
                )
    return icon


ThemedImage = tuple[Image.Image, Image.Image]


def both_themes(
    render: Callable[..., Image.Image],
    *args: Any,
    **kwargs: Any,
) -> ThemedImage:
    """Render a (day, night) pair for CTkImage's light and dark images."""
    return render(*args, night=False, **kwargs), render(*args, night=True, **kwargs)

from __future__ import annotations

import math
import random

from PIL import Image, ImageDraw, ImageFont, ImageOps

from .constants import (
    ACCENT,
    ACCENT_DARK,
    ALBUM_ART_SIZE,
    BACKGROUND,
    INK,
    MUTED,
)

# Lightest to darkest; a leading space lets highlights fall away to paper.
GLYPH_RAMP = " .`:-~=+*xo#%@"
NOISE_GLYPHS = " " * 14 + ".,`'-:;~+*"
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
) -> None:
    rows = FIGURE
    draw = ImageDraw.Draw(canvas)
    top = bottom - len(rows) * pixel
    width = len(rows[0]) * pixel
    # Clear a little paper around the figure so it reads against dense noise.
    draw.rectangle(
        (left - pixel, top - pixel, left + width + pixel, bottom + pixel),
        fill=BACKGROUND,
    )
    for row_index, row in enumerate(rows):
        for column_index, cell in enumerate(row):
            if cell == ".":
                continue
            x = left + column_index * pixel
            y = top + row_index * pixel
            draw.rectangle(
                (x, y, x + pixel - 1, y + pixel - 1),
                fill=ACCENT_DARK if cell == "O" else ACCENT,
            )


def render_ascii_art(
    source: Image.Image | None,
    size: int = ALBUM_ART_SIZE * 2,
    seed: int | str | None = None,
) -> Image.Image:
    """Redraw an image as dithered glyph noise on bone paper."""
    rng = random.Random(seed)
    cell_width, cell_height = 5, 8
    columns, rows = size // cell_width, size // cell_height
    if source is None:
        tones = landscape(columns, rows, rng.randrange(1 << 30))
    else:
        tones = ImageOps.autocontrast(
            ImageOps.fit(source.convert("L"), (columns, rows)),
            cutoff=2,
        )

    canvas = Image.new("RGB", (size, size), BACKGROUND)
    draw = ImageDraw.Draw(canvas)
    font = load_glyph_font(cell_height + 1)
    ink = hex_to_rgb(INK)
    muted = hex_to_rgb(MUTED)
    last_glyph = len(GLYPH_RAMP) - 1
    for y in range(rows):
        for x in range(columns):
            darkness = 1 - tones.getpixel((x, y)) / 255
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

    pixel = max(2, size // 60)
    draw_figure(
        canvas,
        left=round(size * 0.18),
        bottom=round(size * 0.86),
        pixel=pixel,
    )
    return canvas


def noise_line(length: int, rng: random.Random | None = None) -> str:
    rng = rng or random.Random()
    return "".join(rng.choice(NOISE_GLYPHS) for _ in range(length))


def drift_noise(line: str, amount: float, rng: random.Random) -> str:
    """Flicker a fraction of the characters, like a weak terminal signal."""
    characters = list(line)
    for _ in range(max(1, round(len(characters) * amount))):
        characters[rng.randrange(len(characters))] = rng.choice(NOISE_GLYPHS)
    return "".join(characters)

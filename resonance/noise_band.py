from __future__ import annotations

import random

import customtkinter

from .ascii_art import drift_noise, noise_line
from .constants import FAINT, MONO_FONT
from .windows import cancel_pending_after

FLICKER_MS = 160
FLICKER_AMOUNT = 0.05


class NoiseBand(customtkinter.CTkLabel):
    """Rows of faint, flickering ASCII noise, like a starfield.

    ``densities`` gives each row's share of marks, top row first, so a
    band can thin out towards the content.
    """

    def __init__(
        self,
        parent: customtkinter.CTkBaseClass | customtkinter.CTkToplevel,
        columns: int,
        densities: tuple[float, ...],
    ) -> None:
        self.rng = random.Random()
        self.densities = densities
        super().__init__(
            parent,
            text="\n".join(
                noise_line(columns, self.rng, density) for density in densities
            ),
            font=customtkinter.CTkFont(family=MONO_FONT, size=8),
            text_color=FAINT,
            height=len(densities) * 11,
        )
        self.after(FLICKER_MS, self.flicker)

    def flicker(self) -> None:
        rows = self.cget("text").split("\n")
        self.configure(
            text="\n".join(
                drift_noise(row, FLICKER_AMOUNT, self.rng, density)
                for row, density in zip(rows, self.densities)
            )
        )
        self.after(FLICKER_MS, self.flicker)

    def destroy(self) -> None:
        cancel_pending_after(self)
        super().destroy()

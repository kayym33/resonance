"""Short sound effects, played without blocking and never raising.

The only one so far is the tick for completing a habit. It is synthesised
(no audio files to bundle): two very short, bright, noisy snaps with
almost no tone, the second a little softer and lower, over a faint knock.

The sound is written to ``<data folder>/sounds/tick-<version>.wav`` the
first time it's needed, so changing the recipe (bump ``SYNTH_VERSION``)
makes a new file. A WAV saved as ``<data folder>/my-tick.wav`` is played
instead, so anyone can use their own sound.
"""

from __future__ import annotations

import math
import os
import random
import shutil
import struct
import subprocess
import sys
import wave
from dataclasses import dataclass
from pathlib import Path

from .paths import DATA_DIR

SYNTH_VERSION = 1
SOUNDS_DIR = DATA_DIR / "sounds"
CUSTOM_TICK_PATH = DATA_DIR / "my-tick.wav"
RATE = 44100
PEAK = 0.85
# Silence around the sound. Players drop the start of a stream while it
# opens and can stop before a very short one drains, so without this a
# 0.1s click may not be heard at all.
LEAD_IN = 0.05
TAIL = 0.3
# Tried in order on Linux; the first one installed plays the sound.
LINUX_PLAYERS = (("pw-play",), ("paplay",), ("aplay", "-q"))


@dataclass(frozen=True)
class Snap:
    start: float  # seconds
    loudness: float
    # Centre of the noise band, Hz; the release sits a little lower.
    brightness: float = 4200.0


@dataclass(frozen=True)
class Tick:
    snaps: tuple[Snap, ...] = (Snap(0.0, 1.0), Snap(0.07, 0.7, 3600.0))
    # How fast the snap's noise dies away, seconds.
    noise_decay: float = 0.0016
    # Ringing on top of the noise: (Hz, loudness, decay seconds).
    ring: tuple[tuple[float, float, float], ...] = (
        (3150.0, 0.35, 0.0022),
        (5300.0, 0.25, 0.0015),
        (7400.0, 0.15, 0.0010),
    )
    # A low knock under each snap, for body.
    knock: tuple[float, float, float] = (950.0, 0.18, 0.004)
    length: float = 0.14


TICK = Tick()


def band_pass(samples: list[float], centre: float, q: float = 1.2) -> list[float]:
    """A biquad band-pass (RBJ cookbook), so the noise sounds like metal
    rather than hiss."""
    omega = 2 * math.pi * centre / RATE
    alpha = math.sin(omega) / (2 * q)
    b0, b2 = alpha, -alpha
    a0, a1, a2 = 1 + alpha, -2 * math.cos(omega), 1 - alpha
    out: list[float] = []
    x1 = x2 = y1 = y2 = 0.0
    for x in samples:
        y = (b0 * x + b2 * x2 - a1 * y1 - a2 * y2) / a0
        out.append(y)
        x2, x1, y2, y1 = x1, x, y1, y
    return out


def tick_samples(tick: Tick = TICK) -> list[float]:
    rng = random.Random(7)
    total = int(tick.length * RATE)
    samples = [0.0] * total
    for snap in tick.snaps:
        first = int(snap.start * RATE)
        count = total - first
        noise = [
            rng.uniform(-1, 1) * math.exp(-(index / RATE) / tick.noise_decay)
            for index in range(count)
        ]
        noise = band_pass(noise, snap.brightness)
        pitch = snap.brightness / 4200.0
        knock_hz, knock_level, knock_decay = tick.knock
        for index in range(count):
            t = index / RATE
            value = 3.0 * noise[index]
            for frequency, level, decay in tick.ring:
                value += level * math.exp(-t / decay) * math.sin(2 * math.pi * frequency * pitch * t)
            value += knock_level * math.exp(-t / knock_decay) * math.sin(2 * math.pi * knock_hz * t)
            samples[first + index] += snap.loudness * value
    loudest = max(abs(sample) for sample in samples) or 1.0
    lead, tail = [0.0] * int(LEAD_IN * RATE), [0.0] * int(TAIL * RATE)
    return lead + [sample * PEAK / loudest for sample in samples] + tail


def write_wav(path: Path, samples: list[float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = b"".join(
        struct.pack("<h", round(max(-1.0, min(1.0, sample)) * 32767)) for sample in samples
    )
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(RATE)
        wav_file.writeframes(frames)


def tick_path() -> Path:
    if CUSTOM_TICK_PATH.exists():
        return CUSTOM_TICK_PATH
    path = SOUNDS_DIR / f"tick-{SYNTH_VERSION}.wav"
    if not path.exists():
        write_wav(path, tick_samples())
    return path


def play_file(path: Path) -> None:
    if os.name == "nt":
        import winsound

        winsound.PlaySound(
            str(path),
            winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
        )
        return
    if sys.platform == "darwin":
        players: tuple[tuple[str, ...], ...] = (("afplay",),)
    else:
        players = LINUX_PLAYERS
    for player in players:
        program = shutil.which(player[0])
        if program is not None:
            subprocess.Popen(
                [program, *player[1:], str(path)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return


def play_tick() -> None:
    """Silently does nothing if there's no way to play sound."""
    try:
        play_file(tick_path())
    except Exception as error:  # A sound is never worth an error.
        print(f"Couldn't play the tick: {error}", file=sys.stderr)

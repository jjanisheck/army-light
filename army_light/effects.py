"""App-driven effect step generators.

The V4 wand's firmware-effect registers are guarded (blind writes crash the
firmware — see tasks/2026-06-03-effects-menu-design.md), so all effects are
driven by the app over the verified color+commit path. Each effect is an
infinite generator of steps:

    (rgb, transition, delay_s)

`transition` is the wand's fade byte (10ms units, 0 = hard cut); `delay_s` is
how long the controller sleeps before the next step. Pure functions — the
controller's effect task does the I/O.
"""

from __future__ import annotations

import colorsys
import random
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Callable

RGB = tuple[int, int, int]
Step = tuple[RGB, int, float]

OFF: RGB = (0, 0, 0)


def _hsv(h: float, s: float = 1.0, v: float = 1.0) -> RGB:
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
    return (round(r * 255), round(g * 255), round(b * 255))


def blink(rgb: RGB) -> Iterator[Step]:
    """Hard on/off, 0.6s per phase."""
    while True:
        yield (rgb, 0, 0.6)
        yield (OFF, 0, 0.6)


def breath(rgb: RGB) -> Iterator[Step]:
    """Slow fade in/out. transition=120 → 1.2s fade; sleep slightly longer so
    the fade completes before the opposite one starts."""
    while True:
        yield (rgb, 120, 1.3)
        yield (OFF, 120, 1.3)


def strobe(rgb: RGB) -> Iterator[Step]:
    """Rapid hard on/off flashing, 150ms per phase."""
    while True:
        yield (rgb, 0, 0.15)
        yield (OFF, 0, 0.15)


def duo_fade(rgb_a: RGB, rgb_b: RGB) -> Iterator[Step]:
    """Smooth gradient back and forth between two colors (1s fades)."""
    while True:
        yield (rgb_a, 100, 1.1)
        yield (rgb_b, 100, 1.1)


def cycle(steps: int = 24) -> Iterator[Step]:
    """Walk the hue wheel in `steps` increments, fading 0.5s per step
    (~12s per revolution at the default)."""
    wheel = [_hsv(i / steps) for i in range(steps)]
    while True:
        for rgb in wheel:
            yield (rgb, 50, 0.5)


def candle() -> Iterator[Step]:
    """Warm amber base with gentle random flickers."""
    while True:
        v = random.uniform(0.55, 1.0)               # flicker brightness
        h = random.uniform(0.085, 0.11)             # amber hue jitter
        rgb = _hsv(h, 1.0, v)
        yield (rgb, random.randint(5, 25), random.uniform(0.1, 0.45))


# The classic seven, in order.
ROYGBIV: list[RGB] = [
    (255, 0, 0),      # red
    (255, 80, 0),     # orange
    (255, 210, 0),    # yellow
    (0, 255, 0),      # green
    (0, 0, 255),      # blue
    (75, 0, 130),     # indigo
    (160, 0, 255),    # violet
]


def rainbow() -> Iterator[Step]:
    """ROYGBIV in order — a deliberate march: 0.8s fade into each color, then
    hold it, ~2s per color (≈14s per full rainbow)."""
    while True:
        for rgb in ROYGBIV:
            yield (rgb, 80, 2.0)


# Theme palettes (whole-globe — the V4 exposes no per-zone control over BLE).
JUNGLE_COLORS: list[RGB] = [
    (10, 120, 25),    # deep canopy
    (40, 200, 30),    # leaf green
    (120, 220, 40),   # sunlit lime
    (0, 160, 90),     # fern
    (210, 160, 20),   # golden sunlight
    (255, 120, 0),    # tropical flower
    (0, 140, 120),    # rainforest teal
]

ICE_COLORS: list[RGB] = [
    (160, 220, 255),  # pale ice blue
    (90, 170, 255),   # glacier blue
    (0, 200, 255),    # cyan
    (200, 235, 255),  # frost
    (60, 100, 220),   # deep cold blue
    (255, 255, 255),  # sparkle white
]


def jungle() -> Iterator[Step]:
    """Organic rainforest drift — slow green fades with warm sunlit flutters."""
    while True:
        rgb = random.choice(JUNGLE_COLORS)
        if random.random() < 0.2:                 # quick flutter (bird/leaf)
            yield (rgb, 10, random.uniform(0.2, 0.5))
        else:                                     # slow canopy drift
            t = random.randint(80, 180)
            yield (rgb, t, t / 100.0 + random.uniform(0.2, 1.0))


def ice() -> Iterator[Step]:
    """Cold crystalline shimmer with a guaranteed white sparkle every few steps."""
    since_sparkle = 0
    while True:
        if since_sparkle >= 5 or (since_sparkle > 1 and random.random() < 0.15):
            since_sparkle = 0
            yield ((255, 255, 255), 0, 0.25)      # sharp glint
        else:
            since_sparkle += 1
            rgb = random.choice([c for c in ICE_COLORS if c != (255, 255, 255)])
            t = random.randint(60, 150)
            yield (rgb, t, t / 100.0 + random.uniform(0.2, 0.8))


def party() -> Iterator[Step]:
    """Random saturated colors at a beat-ish pace — mostly hard cuts, some fades."""
    hue = random.random()
    while True:
        hue = (hue + random.uniform(0.15, 0.6)) % 1.0  # always a visible jump
        transition = 0 if random.random() < 0.7 else 40
        yield (_hsv(hue), transition, 0.45)


@dataclass(frozen=True)
class Effect:
    steps: Callable[..., Iterator[Step]]
    arity: int  # how many colors the effect takes (0, 1, or 2)


# Menu order. Labels are what the UI shows and what the controller reports.
EFFECTS: dict[str, Effect] = {
    "Blink": Effect(blink, arity=1),
    "Breath": Effect(breath, arity=1),
    "Strobe": Effect(strobe, arity=1),
    "Duo Fade": Effect(duo_fade, arity=2),
    "Color Cycle": Effect(cycle, arity=0),
    "Rainbow": Effect(rainbow, arity=0),
    "Candle": Effect(candle, arity=0),
    "Party": Effect(party, arity=0),
    "Jungle": Effect(jungle, arity=0),
    "Ice": Effect(ice, arity=0),
}

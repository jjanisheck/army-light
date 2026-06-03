"""The menu color palette and named-color lookup."""

from __future__ import annotations

RGB = tuple[int, int, int]

# Menu order, top to bottom. (label, (r, g, b)). "Off" renders as its own
# menu section, not in the COLORS grid.
PALETTE: list[tuple[str, RGB]] = [
    ("Red", (255, 0, 0)),
    ("Orange", (255, 80, 0)),
    ("Amber", (255, 150, 0)),
    ("Yellow", (255, 210, 0)),
    ("Lime", (160, 255, 0)),
    ("Green", (0, 255, 0)),
    ("Mint", (0, 255, 150)),
    ("Cyan", (0, 200, 255)),
    ("Sky", (80, 140, 255)),
    ("Blue", (0, 0, 255)),
    ("ARMY Purple", (130, 60, 255)),
    ("Purple", (160, 0, 255)),
    ("Magenta", (255, 0, 255)),
    ("Pink", (255, 40, 150)),
    ("Rose", (255, 120, 170)),
    ("White", (255, 255, 255)),
    ("Off", (0, 0, 0)),
]

# Lowercased name -> rgb, for `probe --color red` etc.
BY_NAME: dict[str, RGB] = {label.lower(): rgb for label, rgb in PALETTE}


def parse_color(text: str) -> RGB:
    """Accept a palette name ('red'), 'r,g,b', or '#rrggbb'."""
    t = text.strip().lower()
    if t in BY_NAME:
        return BY_NAME[t]
    if t.startswith("#") and len(t) == 7:
        return (int(t[1:3], 16), int(t[3:5], 16), int(t[5:7], 16))
    if "," in t:
        parts = [int(p) for p in t.split(",")]
        if len(parts) == 3 and all(0 <= p <= 255 for p in parts):
            return (parts[0], parts[1], parts[2])
    raise ValueError(f"Can't parse color {text!r} (try 'red', '255,0,0', or '#ff0000').")

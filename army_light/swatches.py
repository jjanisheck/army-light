"""Menu swatch icons — tiny rounded-square PNGs rendered with the stdlib.

rumps.MenuItem takes an icon *path*, so swatches are rendered once per color
into `support_dir()/swatches/` and reused (cached by hex name). Pure
zlib/struct PNG writing keeps the app dependency-free.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

from .config import support_dir

RGB = tuple[int, int, int]

SIZE = 28      # px (rendered @2x by AppKit; menu shows ~14pt)
RADIUS = 7     # corner radius, px
BORDER = (120, 120, 120, 90)  # subtle outline so white/black swatches read


def _chunk(tag: bytes, data: bytes) -> bytes:
    return (struct.pack(">I", len(data)) + tag + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))


def _coverage(x: int, y: int) -> float:
    """1.0 inside the rounded square, 0.0 outside (hard mask, soft corners)."""
    lo, hi = RADIUS - 0.5, SIZE - RADIUS - 0.5
    cx = min(max(x, lo), hi)
    cy = min(max(y, lo), hi)
    d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
    return max(0.0, min(1.0, RADIUS - d + 0.5))


def _render(rgb: RGB) -> bytes:
    r, g, b = rgb
    br, bg, bb, ba = BORDER
    rows = []
    for y in range(SIZE):
        row = bytearray(b"\x00")  # filter type 0
        for x in range(SIZE):
            cov = _coverage(x, y)
            edge = cov - _coverage_inner(x, y)
            if cov <= 0:
                row += b"\x00\x00\x00\x00"
            elif edge > 0:  # blend the outline over the fill at the rim
                row += bytes([
                    round(r + (br - r) * edge * ba / 255),
                    round(g + (bg - g) * edge * ba / 255),
                    round(b + (bb - b) * edge * ba / 255),
                    round(255 * cov),
                ])
            else:
                row += bytes([r, g, b, round(255 * cov)])
        rows.append(bytes(row))
    return b"".join(rows)


def _coverage_inner(x: int, y: int) -> float:
    """Coverage of the shape shrunk by ~1.5px — used to find the rim."""
    lo, hi = RADIUS - 0.5, SIZE - RADIUS - 0.5
    cx = min(max(x, lo), hi)
    cy = min(max(y, lo), hi)
    d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
    return max(0.0, min(1.0, (RADIUS - 1.5) - d + 0.5))


def swatch_path(rgb: RGB) -> Path:
    """Path to the PNG swatch for `rgb`, rendering it on first use."""
    d = support_dir() / "swatches"
    d.mkdir(parents=True, exist_ok=True)
    path = d / "{:02x}{:02x}{:02x}.png".format(*rgb)
    if path.exists():
        return path
    ihdr = struct.pack(">IIBBBBB", SIZE, SIZE, 8, 6, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr)
           + _chunk(b"IDAT", zlib.compress(_render(rgb)))
           + _chunk(b"IEND", b""))
    path.write_bytes(png)
    return path

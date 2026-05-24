"""Packet-format registry.

The wand's encoding is pluggable so the `probe` tool can try several formats and
the menu app can switch via config without code edits. `fanlight` is the verified
ARMY Bomb / Fanlight-family format; the others are common generic formats kept as
probe fallbacks in case a different firmware revision turns up.
"""

from __future__ import annotations

from typing import Callable

RGB = tuple[int, int, int]


def fanlight(r: int, g: int, b: int) -> bytes:
    """BTS ARMY Bomb / Fanlight family.

        01 01 0B 00 00 RR GG BB 00 00 CK
        CK = (sum of bytes[2..9]) & 0xFF == (0x0B + R + G + B) & 0xFF

    Verified against P1Harmony and LOONA/Loossemble sticks (same platform).
    Decompiled setColor() sums bytes[2..10] with byte[10]=0 during the sum.
    """
    body = [0x0B, 0x00, 0x00, r, g, b, 0x00, 0x00]
    checksum = sum(body) & 0xFF
    return bytes([0x01, 0x01, *body, checksum])


def triones(r: int, g: int, b: int) -> bytes:
    """Common 'Triones'/'magic' bulbs: 56 RR GG BB 00 F0 AA (char 0xffe1)."""
    return bytes([0x56, r, g, b, 0x00, 0xF0, 0xAA])


def elk_bledom(r: int, g: int, b: int) -> bytes:
    """ELK-BLEDOM strips: 7E 00 05 03 RR GG BB 00 EF."""
    return bytes([0x7E, 0x00, 0x05, 0x03, r, g, b, 0x00, 0xEF])


def raw_rgb(r: int, g: int, b: int) -> bytes:
    """Bare three-byte RGB, no header/checksum."""
    return bytes([r, g, b])


# Ordered: the verified format first so `probe` tries the likely winner first.
FORMATS: dict[str, Callable[[int, int, int], bytes]] = {
    "fanlight": fanlight,
    "triones": triones,
    "elk_bledom": elk_bledom,
    "raw_rgb": raw_rgb,
}


def build(fmt: str, r: int, g: int, b: int) -> bytes:
    try:
        return FORMATS[fmt](r, g, b)
    except KeyError:
        raise ValueError(
            f"Unknown packet format {fmt!r}. Known: {', '.join(FORMATS)}"
        ) from None


# Non-color Fanlight query packets (01 01 06 50 XX CK, CK = byte2+byte3+byte4).
# Handy for `monitor` to elicit a notification response from the wand.
QUERY_BATTERY = bytes([0x01, 0x01, 0x06, 0x50, 0x07, 0x5D])
QUERY_FIRMWARE = bytes([0x01, 0x01, 0x06, 0x50, 0x03, 0x59])
QUERY_HARDWARE = bytes([0x01, 0x01, 0x06, 0x50, 0x04, 0x5A])

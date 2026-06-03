"""Swatch generator tests — valid PNG files, cached by color."""

import struct
import zlib

import pytest

from army_light import swatches


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("ARMYLIGHT_HOME", str(tmp_path))


def _png_chunks(data):
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    pos, chunks = 8, {}
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        tag = data[pos + 4:pos + 8]
        chunks[tag] = data[pos + 8:pos + 8 + length]
        pos += 12 + length
    return chunks


def test_swatch_is_a_valid_rgba_png():
    path = swatches.swatch_path((255, 0, 0))
    chunks = _png_chunks(path.read_bytes())
    w, h, depth, color_type = struct.unpack(">IIBB", chunks[b"IHDR"][:10])
    assert w == h == swatches.SIZE
    assert (depth, color_type) == (8, 6)  # 8-bit RGBA
    assert b"IEND" in chunks


def test_swatch_pixels_carry_the_color_with_rounded_corners():
    path = swatches.swatch_path((10, 200, 30))
    chunks = _png_chunks(path.read_bytes())
    raw = zlib.decompress(chunks[b"IDAT"])
    stride = swatches.SIZE * 4 + 1
    mid = swatches.SIZE // 2
    center = raw[mid * stride + 1 + mid * 4:][:4]
    assert center[:3] == bytes([10, 200, 30]) and center[3] == 255  # opaque center
    corner = raw[1:5]
    assert corner[3] == 0  # transparent corner (rounded)


def test_swatch_is_cached_per_color():
    p1 = swatches.swatch_path((1, 2, 3))
    mtime = p1.stat().st_mtime_ns
    p2 = swatches.swatch_path((1, 2, 3))
    assert p1 == p2 and p2.stat().st_mtime_ns == mtime  # not re-rendered
    assert swatches.swatch_path((4, 5, 6)) != p1

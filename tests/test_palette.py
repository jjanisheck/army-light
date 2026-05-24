"""Color-parsing tests."""

import pytest

from army_light import palette


@pytest.mark.parametrize(
    "text, expected",
    [
        ("red", (255, 0, 0)),
        ("Red", (255, 0, 0)),
        ("OFF", (0, 0, 0)),
        ("255,0,0", (255, 0, 0)),
        (" 0, 200, 255 ", (0, 200, 255)),
        ("#00ff00", (0, 255, 0)),
        ("#FFFFFF", (255, 255, 255)),
    ],
)
def test_parse_color_ok(text, expected):
    assert palette.parse_color(text) == expected


@pytest.mark.parametrize("text", ["", "notacolor", "256,0,0", "1,2", "#fff", "#gggggg"])
def test_parse_color_rejects_bad_input(text):
    with pytest.raises(ValueError):
        palette.parse_color(text)


def test_palette_and_lookup_agree():
    assert palette.BY_NAME["red"] == (255, 0, 0)
    assert all(label.lower() in palette.BY_NAME for label, _ in palette.PALETTE)
    assert ("Off", (0, 0, 0)) in palette.PALETTE

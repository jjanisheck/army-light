"""Packet-format tests. These lock in the verified ARMY Bomb / Fanlight bytes —
if someone "tidies" the builder and breaks the checksum, these fail."""

import pytest

from army_light import packets


def test_fanlight_red_exact_bytes():
    # Verified value from decompiled official source + two working clients.
    assert packets.build("fanlight", 255, 0, 0).hex(" ") == "01 01 0b 00 00 ff 00 00 00 00 0a"


def test_fanlight_white_exact_bytes():
    assert packets.build("fanlight", 255, 255, 255).hex(" ") == "01 01 0b 00 00 ff ff ff 00 00 08"


def test_fanlight_off_exact_bytes():
    assert packets.build("fanlight", 0, 0, 0).hex(" ") == "01 01 0b 00 00 00 00 00 00 00 0b"


@pytest.mark.parametrize("rgb", [(0, 0, 0), (255, 255, 255), (12, 34, 56), (200, 1, 99)])
def test_fanlight_checksum_invariant(rgb):
    pkt = packets.fanlight(*rgb)
    assert len(pkt) == 11
    assert pkt[10] == (sum(pkt[2:10]) & 0xFF)  # checksum = sum of bytes[2..9]


def test_other_formats_shapes():
    assert packets.triones(1, 2, 3) == bytes([0x56, 1, 2, 3, 0x00, 0xF0, 0xAA])
    assert packets.elk_bledom(1, 2, 3) == bytes([0x7E, 0x00, 0x05, 0x03, 1, 2, 3, 0x00, 0xEF])
    assert packets.raw_rgb(1, 2, 3) == bytes([1, 2, 3])


def test_build_unknown_format_raises():
    with pytest.raises(ValueError):
        packets.build("nope", 1, 2, 3)


def test_fanlight_is_the_default_registry_entry():
    # First registry key is what `probe` tries first; keep the verified one first.
    assert next(iter(packets.FORMATS)) == "fanlight"


def test_query_packet_checksums():
    for q in (packets.QUERY_BATTERY, packets.QUERY_FIRMWARE, packets.QUERY_HARDWARE):
        assert q[-1] == (q[2] + q[3] + q[4]) & 0xFF

"""WandController write-sequence tests with a fake BLE client.

Connection model (verified on a real V4 unit, 2026-06-03): the commit byte to
ff13 is NOT a per-write commit — the wand drops the link ~1-2s after every ff13
write (a session restart), which is also how it leaves its power-on pairing
animation. So the controller "latches" ONCE per fresh connection (color + ff13,
expect the drop, reconnect) and then streams plain ff01 color writes over a
persistent link with no further commits.
"""

import asyncio

import pytest

from army_light import packets
from army_light.config import Settings
from army_light.controller import WandController


class FakeClient:
    is_connected = True

    def __init__(self):
        self.writes = []  # (uuid, bytes, response)

    async def write_gatt_char(self, uuid, data, response=False):
        self.writes.append((uuid, bytes(data), response))

    async def disconnect(self):
        pass


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("ARMYLIGHT_HOME", str(tmp_path))


def run_set_color(settings) -> FakeClient:
    fake = FakeClient()

    async def main():
        # Constructed inside the loop: WandController.__init__ creates an
        # asyncio.Lock, which on Python 3.9 requires a current event loop.
        ctl = WandController(settings)
        ctl.LATCH_DELAY = 0  # no need to wait for a fake wand to restart

        async def fake_connect():
            ctl.client = fake
            ctl.connected = True
            return True

        ctl._connect = fake_connect
        await ctl._set_color((255, 0, 0))

    asyncio.run(main())
    return fake


def test_set_color_latches_once_then_writes_color():
    s = Settings()  # V4 defaults: commit char set
    fake = run_set_color(s)
    red = packets.build("bts_v4", 255, 0, 0)
    assert fake.writes == [
        # Fresh connection → latch: color + session-restart byte (wand drops
        # the link), then after the reconnect the color is written plainly.
        (s.color_char_uuid, red, True),
        (s.commit_char_uuid, packets.BTS_V4_COMMIT, False),
        (s.color_char_uuid, red, True),
    ]


def test_set_color_skips_commit_when_unset():
    s = Settings(commit_char_uuid="", packet_format="fanlight")
    fake = run_set_color(s)
    assert len(fake.writes) == 1
    assert fake.writes[0][0] == s.color_char_uuid
    assert fake.writes[0][1] == packets.build("fanlight", 255, 0, 0)


def _wired_controller(s):
    """Controller with a FakeClient patched in (must run inside a loop)."""
    ctl = WandController(s)
    ctl.LATCH_DELAY = 0
    fake = FakeClient()

    async def fake_connect():
        ctl.client = fake
        ctl.connected = True
        return True

    ctl._connect = fake_connect
    return ctl, fake


def test_effect_streams_over_one_latched_connection():
    s = Settings()

    async def main():
        ctl, fake = _wired_controller(s)
        steps = iter([((255, 0, 0), 120, 0.0), ((0, 0, 0), 120, 0.0)])
        await ctl._run_effect(steps)
        return fake

    fake = asyncio.run(main())
    p1 = packets.bts_v4(255, 0, 0, transition=120)
    p2 = packets.bts_v4(0, 0, 0, transition=120)
    assert fake.writes == [
        # First step latches the fresh connection, later steps stream plainly.
        (s.color_char_uuid, p1, True),
        (s.commit_char_uuid, packets.BTS_V4_COMMIT, False),
        (s.color_char_uuid, p1, True),
        (s.color_char_uuid, p2, True),
    ]


def test_brightness_scales_writes_but_not_logical_color():
    s = Settings()

    async def main():
        ctl, fake = _wired_controller(s)
        ctl.brightness = 0.5
        await ctl._set_color((255, 0, 0))
        return ctl, fake

    ctl, fake = asyncio.run(main())
    scaled = packets.build("bts_v4", 128, 0, 0)
    # Every write (latch + stream) carries the scaled color…
    assert [w[1] for w in fake.writes if w[0] == s.color_char_uuid] == [scaled, scaled]
    # …but the controller remembers the logical color for the UI/effects.
    assert ctl.last_rgb == (255, 0, 0)


def test_start_effect_accepts_two_colors():
    s = Settings()

    async def main():
        ctl, _fake = _wired_controller(s)
        await ctl._start_effect("Duo Fade", ((130, 60, 255), (255, 40, 150)))
        assert ctl.current_effect == "Duo Fade"
        ctl._cancel_effect()

    asyncio.run(main())


def test_reconnect_drops_link_and_forces_fresh_resolution():
    s = Settings()

    async def main():
        ctl = WandController(s)
        ctl.LATCH_DELAY = 0
        ctl.address = "STALE-CACHED-ADDRESS"
        fake = FakeClient()
        connect_addresses = []

        async def fake_connect():
            connect_addresses.append(ctl.address)
            ctl.client = fake
            ctl.connected = True
            return True

        ctl._connect = fake_connect
        await ctl._reconnect()
        # Old link dropped, cached address cleared BEFORE any reconnect, so
        # every connect attempt (incl. the latch's) re-scans.
        assert connect_addresses and all(a == "" for a in connect_addresses)
        assert ctl.connected

    asyncio.run(main())


def test_set_color_cancels_running_effect():
    s = Settings()

    async def main():
        ctl, fake = _wired_controller(s)
        await ctl._start_effect("Blink", (255, 0, 0))
        assert ctl.current_effect == "Blink"
        await asyncio.sleep(0)  # let the effect task start
        await ctl._set_color((0, 255, 0))
        assert ctl.current_effect is None
        assert ctl._effect_task is None or ctl._effect_task.cancelled()

    asyncio.run(main())

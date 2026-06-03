"""Control-server tests — localhost HTTP remote (Stream Deck / Shortcuts / curl).

The server translates GET paths into controller calls; a stub controller
records them. Bound to port 0 (ephemeral) so tests never collide.
"""

import json
import urllib.error
import urllib.request

import pytest

from army_light.server import ControlServer


class StubController:
    def __init__(self):
        self.calls = []
        self.connected = True
        self.current_effect = None
        self.last_rgb = (255, 0, 0)
        self.brightness = 1.0

    def set_color(self, rgb):
        self.calls.append(("set_color", rgb))

    def start_effect(self, label, colors=None):
        self.calls.append(("start_effect", label, colors))

    def stop_effect(self):
        self.calls.append(("stop_effect",))

    def set_brightness(self, value):
        self.calls.append(("set_brightness", value))

    def reconnect(self):
        self.calls.append(("reconnect",))


@pytest.fixture()
def remote():
    ctl = StubController()
    server = ControlServer(ctl, port=0)
    server.start()
    yield ctl, f"http://127.0.0.1:{server.port}"
    server.stop()


def get(url):
    with urllib.request.urlopen(url, timeout=5) as r:
        return r.status, json.loads(r.read())


def test_color_by_name_hex_and_rgb(remote):
    ctl, base = remote
    assert get(f"{base}/color/red")[0] == 200
    assert get(f"{base}/color/army-purple")[0] == 200
    assert get(f"{base}/color/00ff7f")[0] == 200
    assert get(f"{base}/color/1,2,3")[0] == 200
    assert ctl.calls == [
        ("set_color", (255, 0, 0)),
        ("set_color", (130, 60, 255)),
        ("set_color", (0, 255, 127)),
        ("set_color", (1, 2, 3)),
    ]


def test_effect_with_label_normalization_and_colors(remote):
    ctl, base = remote
    assert get(f"{base}/effect/glow-cycle")[0] == 200
    assert get(f"{base}/effect/Blink?color=blue")[0] == 200
    assert get(f"{base}/effect/duo-fade?color=red&color2=blue")[0] == 200
    assert ctl.calls == [
        ("start_effect", "Glow Cycle", None),
        ("start_effect", "Blink", (0, 0, 255)),
        ("start_effect", "Duo Fade", ((255, 0, 0), (0, 0, 255))),
    ]


def test_off_stop_brightness_reconnect_status(remote):
    ctl, base = remote
    assert get(f"{base}/off")[0] == 200
    assert get(f"{base}/stop")[0] == 200
    assert get(f"{base}/brightness/40")[0] == 200
    assert get(f"{base}/reconnect")[0] == 200
    assert ctl.calls == [
        ("set_color", (0, 0, 0)),
        ("stop_effect",),
        ("set_brightness", 0.4),
        ("reconnect",),
    ]
    status, body = get(f"{base}/status")
    assert status == 200
    assert body["connected"] is True and body["color"] == [255, 0, 0]


def test_unknown_paths_and_bad_values_are_4xx(remote):
    ctl, base = remote
    for path in ("/nope", "/color/notacolor", "/effect/notaneffect",
                 "/brightness/oops"):
        with pytest.raises(urllib.error.HTTPError) as e:
            get(f"{base}{path}")
        assert e.value.code in (400, 404)
    assert ctl.calls == []

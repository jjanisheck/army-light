"""Generate the Stream Deck plugin manifest + icons from the app's own
palette and effects registries, so the deck always mirrors the Mac app.

Run from the repo root:  python streamdeck/generate.py
"""

import json
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from army_light.effects import EFFECTS  # noqa: E402
from army_light.palette import PALETTE  # noqa: E402

PLUGIN = Path(__file__).resolve().parent / "com.armylight.control.sdPlugin"
IMAGES = PLUGIN / "images"

BRIGHTNESS_PRESETS = [10, 25, 50, 75, 100]
COMMANDS = [("off", "Off"), ("stop", "Stop Effect"), ("reconnect", "Reconnect")]

# Icon stripe themes for arity-0 effects; arity>=1 use the app's default colors.
FX_THEMES = {
    "Color Cycle": [(255, 0, 0), (255, 210, 0), (0, 255, 0), (0, 200, 255), (0, 0, 255), (255, 0, 255)],
    "Rainbow": [(255, 0, 0), (255, 80, 0), (255, 210, 0), (0, 255, 0), (0, 0, 255),
                (75, 0, 130), (160, 0, 255)],
    "Glow Cycle": [(26, 0, 48), (160, 0, 255), (26, 0, 48), (0, 200, 255), (26, 0, 48)],
    "Candle": [(255, 150, 20), (255, 200, 80), (180, 90, 0)],
    "Party": [(255, 0, 64), (0, 224, 255), (255, 224, 0), (160, 0, 255)],
    "Jungle": [(10, 120, 25), (120, 220, 40), (210, 160, 20), (0, 140, 120)],
    "Ice": [(160, 220, 255), (90, 170, 255), (255, 255, 255), (60, 100, 220)],
    "Blink": [(130, 60, 255), (29, 29, 31), (130, 60, 255)],
    "Breath": [(40, 18, 80), (130, 60, 255), (40, 18, 80)],
    "Strobe": [(130, 60, 255), (255, 255, 255), (130, 60, 255), (255, 255, 255)],
    "Duo Fade": [(130, 60, 255), (255, 40, 150)],
}


def slug(name: str) -> str:
    return name.lower().replace(" ", "-")


def _chunk(tag, data):
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)


def _cov(x, y, size, r):
    lo, hi = r - 0.5, size - r - 0.5
    cx = min(max(x, lo), hi)
    cy = min(max(y, lo), hi)
    d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
    return max(0.0, min(1.0, r - d + 0.5))


def png(path, size, stripes, radius_frac=0.25):
    r = size * radius_frac
    n = len(stripes)
    rows = []
    for y in range(size):
        row = bytearray(b"\x00")
        for x in range(size):
            a = _cov(x, y, size, r)
            col = stripes[min(int(x * n / size), n - 1)]
            row += bytes([col[0], col[1], col[2], round(255 * a)])
        rows.append(bytes(row))
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr)
                     + _chunk(b"IDAT", zlib.compress(b"".join(rows))) + _chunk(b"IEND", b""))


def icon(name, stripes):
    png(IMAGES / f"{name}.png", 20, stripes)
    png(IMAGES / f"{name}@2x.png", 40, stripes)
    return f"images/{name}"


def action(uuid, name, icon_path, tooltip, pi=None):
    a = {
        "UUID": uuid,
        "Name": name,
        "Tooltip": tooltip,
        "Icon": icon_path,
        "SupportedInMultiActions": True,
        "States": [{"Image": "images/key"}],
    }
    if pi:
        a["PropertyInspectorPath"] = pi
    return a


def main():
    actions = []

    # Ready-made color keys (every Mac-app swatch).
    for label, rgb in PALETTE:
        if label == "Off":
            continue
        actions.append(action(
            f"com.armylight.preset.color.{slug(label)}", label,
            icon(f"p-{slug(label)}", [rgb]),
            f"Set the wand to {label}.",
        ))

    # Ready-made effect keys.
    for label in EFFECTS:
        actions.append(action(
            f"com.armylight.preset.fx.{slug(label)}", label,
            icon(f"fx-{slug(label)}", FX_THEMES.get(label, [(130, 60, 255)])),
            f"Start the {label} effect.",
        ))

    # Brightness presets.
    for pct in BRIGHTNESS_PRESETS:
        shade = round(60 + 195 * pct / 100)
        actions.append(action(
            f"com.armylight.preset.bright.{pct}", f"Brightness {pct}%",
            icon(f"b-{pct}", [(shade, round(shade * 0.82), 0)]),
            f"Set brightness to {pct}%.",
        ))

    # Commands.
    cmd_colors = {"off": [(44, 44, 46)], "stop": [(142, 44, 44)], "reconnect": [(44, 90, 142)]}
    for cmd, label in COMMANDS:
        actions.append(action(
            f"com.armylight.preset.cmd.{cmd}", label,
            icon(f"c-{cmd}", cmd_colors[cmd]),
            f"{label}.",
        ))

    # Configurable actions (custom colors, per-effect colors, any percent).
    actions += [
        action("com.armylight.color", "Custom Color", "images/color",
               "Any color — palette dropdown or full color picker.", "pi/color.html"),
        action("com.armylight.effect", "Custom Effect", "images/effect",
               "Any effect, with per-effect color pickers.", "pi/effect.html"),
        action("com.armylight.brightness", "Custom Brightness", "images/brightness",
               "Any brightness percent.", "pi/brightness.html"),
        action("com.armylight.command", "Custom Command", "images/command",
               "Off, Stop Effect, or Reconnect.", "pi/command.html"),
    ]

    manifest = {
        "SDKVersion": 2,
        "CodePath": "index.html",
        "Name": "ARMY Light",
        "Author": "army-light",
        "Version": "1.1.0",
        "Description": "Control a BTS ARMY Bomb Ver. 4 through the ARMY Light macOS app: "
                       "every color, effect, and brightness preset as a ready-made key. "
                       "Requires the ARMY Light app running (localhost remote on port 8722).",
        "URL": "https://github.com/jjanisheck/army-light",
        "Icon": "images/plugin",
        "Category": "ARMY Light",
        "CategoryIcon": "images/category",
        "Software": {"MinimumVersion": "6.0"},
        "OS": [{"Platform": "mac", "MinimumVersion": "12"}],
        "Actions": actions,
    }
    (PLUGIN / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"manifest: {len(actions)} actions; icons regenerated in {IMAGES}")


if __name__ == "__main__":
    main()

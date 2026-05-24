# ARMY Light

Set your BTS **ARMY Bomb** lightstick to any color from the macOS menu bar — no
phone app required. Click a color, the wand changes color.

```
 💡  ARMY Light
 ┌──────────────┐
 │ Red          │
 │ Orange       │
 │ Yellow       │
 │ Green        │
 │ Cyan         │
 │ Blue         │
 │ Purple       │
 │ Pink         │
 │ White        │
 │ Off          │
 │ ───────────  │
 │ ● Connected  │
 │ ───────────  │
 │ Test (Red)   │
 │ Quit         │
 └──────────────┘
```

## Get the app

**Option A — download (easiest).** Grab the latest `ARMY Light.app` from the
[Releases page](https://github.com/USERNAME/army-light/releases), unzip it, and
drag it to **Applications**. (Unsigned build: first launch → right-click → **Open**.)

**Option B — build it yourself.**

```bash
git clone https://github.com/USERNAME/army-light.git
cd army-light
make dev          # create a venv + install
make app          # build dist/ARMY Light.app
open "dist/ARMY Light.app"
```

Drag `dist/ARMY Light.app` to **Applications** to keep it, and add it to **Login
Items** to start at boot.

## Use it

1. Set the wand's switch to **Bluetooth mode** and make sure it's **not connected
   to the phone app** (only one device can control it at a time).
2. Launch ARMY Light — a 💡 appears in the menu bar.
3. Click a color. The first click connects (~1–3s); after that it's instant.

Bluetooth permission: macOS asks once on first use — allow it. If colors don't
work, see the [install & troubleshooting guide](docs/INSTALL.md).

## Requirements

macOS with Bluetooth, and a BTS ARMY Bomb. Building from source needs Python 3.9+.

## How it works

A tiny menu-bar app (`rumps`) on the main thread, all Bluetooth (`bleak`) on a
background thread. It speaks the **Fanlight** BLE protocol the official BTS app
uses. Full details — architecture, the verified packet format, and the discovery
CLI for confirming/extending support — are in **[docs/PROTOCOL.md](docs/PROTOCOL.md)**.

> Status: the protocol is verified against sibling Fanlight sticks (P1Harmony,
> LOONA). If a color doesn't take on your unit, the built-in `army-light probe`
> tool finds the right values — see the protocol doc.

## Run from source (developers)

```bash
make dev
make run          # python -m army_light
make test         # pytest
make lint         # ruff
```

The `army-light` command (after `pip install -e .`) exposes the discovery CLI:
`scan`, `inspect`, `probe`, `monitor`. See [docs/PROTOCOL.md](docs/PROTOCOL.md).

## License

[The Unlicense](LICENSE) — public domain. Do whatever you want.

## Contributing

Issues and PRs welcome. Run `make lint test` before opening a PR. If you confirm
the protocol on a specific ARMY Bomb version, please note it in an issue.

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A macOS menu-bar app that drives a BTS ARMY Bomb lightstick to arbitrary RGB colors
over Bluetooth LE. Click a color in the menu, the wand changes color. It also ships a
discovery CLI (`scan`/`inspect`/`probe`/`monitor`) for verifying the BLE protocol
against a physical wand. User docs: `README.md` (front door), `docs/INSTALL.md`,
`docs/PROTOCOL.md` (architecture + protocol).

## Commands

```bash
make dev          # venv + editable install + dev/build extras
make run          # launch the menu-bar app (python -m army_light)
make test         # pytest
make lint         # ruff check
make app          # build dist/ARMY Light.app (py2app)

python -m army_light scan|inspect <addr>|probe <addr>|monitor <addr>|set-config …
```

`python -m army_light` works with no install. After `pip install -e .` the
`army-light` console command is equivalent. The `.app` bundle is the primary
end-user distribution (py2app config in `packaging/setup_app.py`, entry
`packaging/app_main.py`).

**Gotchas:** Python 3.9 venvs bundle setuptools too old for this project's PEP 621
metadata — `make dev` upgrades it first; doing a bare `pip install -e .` on old
setuptools yields an empty "UNKNOWN" package. Tests/lint don't need rumps/bleak to
import (pure modules), but the menu app and controller do. Validation of the actual
BLE write is still manual (needs the powered-on wand).

## Architecture

`army_light/` package, two threads, bridged by `asyncio.run_coroutine_threadsafe`:

- **Main/AppKit thread** runs `rumps` (`app.py`). AppKit owns the runloop — nothing
  blocking may run here. A `rumps.Timer` polls controller state into the menu (no
  cross-thread UI calls).
- **Background thread** runs `WandController`'s private `asyncio` loop
  (`controller.py`) for all `bleak` BLE work.
- Menu color clicks call `WandController.set_color()`, which schedules a coroutine
  onto the background loop.

`WandController` holds no persistent connection — the wand idle-disconnects, so each
write resolves+connects (preferring the **service UUID**, falling back to a name
substring), writes, and drops the client on failure so the next call reconnects. An
`asyncio.Lock` serializes writes. On connect it optionally subscribes to notifications
and sends a white "wake" packet, mimicking the official app.

Module map: `config.py` (Settings dataclass + JSON persistence in
`~/Library/Application Support/ArmyLight/`, logs in `~/Library/Logs/ArmyLight/`;
relocatable via `ARMYLIGHT_HOME`), `packets.py` (pluggable format registry),
`palette.py` (colors), `discovery.py` (scan/inspect/probe/monitor), `cli.py`
(argparse dispatch), `app.py` (rumps UI).

Repo layout: `army_light/` (package), `tests/` (pytest), `docs/` (INSTALL,
PROTOCOL), `packaging/` (py2app build), `Makefile`, `pyproject.toml` (metadata +
ruff/pytest config). `tasks/` is internal planning (gitignored).

## BLE protocol (verified — Fanlight family)

The official BTS app is built on the shared **Fanlight** platform. Confirmed against
sibling sticks (P1Harmony, LOONA) via decompiled source + two working clients; not yet
against a BTS unit specifically, so `probe` exists to confirm. These are the defaults
in `config.py` / `packets.py` (no longer guesses):

- Service UUID `00010203-0405-0607-0809-0a0b0c0d1911` (used to resolve the wand)
- Write/notify char `00010203-0405-0607-0809-0a0b0c0d2b19`
- Color packet (`fanlight` format): `01 01 0B 00 00 RR GG BB 00 00 CK`,
  `CK = (0x0B + R + G + B) & 0xFF`
- Write-**without**-response (retry with-response on failure); **no auth** for color control

Other packet formats (`triones`, `elk_bledom`, `raw_rgb`) remain in the registry only
as `probe` fallbacks. Sources: github.com/TR0U8L3-gif/kpop-lightsticks,
github.com/gengkev/kpop-lightstick-experiments.

## Operational constraints

- macOS-specific: `bleak` returns a per-Mac CoreBluetooth UUID, not a hardware MAC, so
  a cached `wand_address` isn't portable — resolution prefers the service UUID each run.
- Only one host can own the BLE link — the wand must be unpaired from the phone app and
  its switch set to Bluetooth mode.
- macOS prompts for Bluetooth permission; from a terminal it's attributed to the
  terminal app, from the bundle to ARMY Light. Missing permission = silent zero results.

## Next phase (per STATUS.md)

Swap manual clicks for a notification source (Gmail/IMAP poll → color rules), add an
idle/resting color, and hold an alert color for a fixed interval before returning to
idle. The connect/write layer carries over unchanged.

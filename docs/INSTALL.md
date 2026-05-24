# Install & Troubleshooting

Everything needed to get ARMY Light running, build the `.app`, grant Bluetooth
access, and fix common issues.

---

## Prerequisites

- macOS with Bluetooth.
- A BTS ARMY Bomb, switch in **Bluetooth mode**, **not connected to the phone
  app** (only one device can hold the link at a time).
- To build from source: Python 3.9+ (`python3 --version`).

---

## Build the .app

```bash
git clone https://github.com/USERNAME/army-light.git
cd army-light
make dev          # venv + install (incl. py2app)
make app          # -> dist/ARMY Light.app
open "dist/ARMY Light.app"
```

Drag `dist/ARMY Light.app` to **/Applications** to keep it.

The bundle is a menu-bar agent (`LSUIElement` — no Dock icon) and declares
`NSBluetoothAlwaysUsageDescription`, so macOS attributes the Bluetooth prompt to
ARMY Light itself.

**Unsigned build:** this build isn't code-signed or notarized, so Gatekeeper
blocks the first launch. Right-click the app → **Open** → **Open** once, and macOS
remembers it. (To distribute widely, sign + notarize with an Apple Developer ID.)

**Launch at login:** System Settings → General → Login Items → **＋** → add
`ARMY Light.app`.

---

## Grant Bluetooth permission

The first BLE call triggers a one-time macOS permission prompt — allow it.

- Running the **.app**: the prompt is attributed to *ARMY Light*.
- Running from a **terminal** (dev mode): the prompt is attributed to your
  terminal app (Terminal / iTerm). Grant it under **System Settings → Privacy &
  Security → Bluetooth**.

Gotcha: if permission is missing, scans silently return **zero devices** with no
error. If nothing shows up, check here first.

---

## Run from source (developers)

```bash
make dev          # venv + editable install + dev tools
make run          # launch the menu-bar app (python -m army_light)
make test         # pytest
make lint         # ruff
```

`python -m army_light` works with no install at all (just
`pip install -r requirements.txt`). The `army-light` console command requires an
editable install; `make dev` upgrades setuptools first (Python 3.9 venvs ship a
version too old for this project's metadata, which otherwise installs an empty
"UNKNOWN" package).

Config and logs live under `~/Library/Application Support/ArmyLight/` and
`~/Library/Logs/ArmyLight/`. Set `ARMYLIGHT_HOME=/some/dir` to relocate both.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Nothing in the menu bar | The icon is a small 💡/🔅 near the clock. Quit other instances; relaunch. |
| `scan` / app finds no wand | Grant Bluetooth (above). Confirm the wand is on, switch in **Bluetooth mode**, and disconnected from the phone app. |
| Wand never appears | It only advertises when on and not already connected. Disconnect from the phone, power-cycle, try again. |
| Connects but color does nothing | Confirm the protocol with `army-light probe <addr>` (see [PROTOCOL.md](PROTOCOL.md)), then `army-light set-config …`. Check `~/Library/Logs/ArmyLight/army_light.log`. |
| Writes fail intermittently | Expected — the wand idle-disconnects and each click reconnects. Keep it on wall power for snappier reconnects. |
| Connect hangs | Make sure no other device (the phone) holds the connection. Power-cycle the wand. |
| "ARMY Light is damaged / can't be opened" | Unsigned build — right-click → **Open** the first time. |
| Permission prompt never appeared | Toggle the app/terminal off and on under Privacy & Security → Bluetooth, then retry. |

The discovery CLI (`scan`, `inspect`, `probe`, `monitor`) and the protocol itself
are documented in **[PROTOCOL.md](PROTOCOL.md)**.

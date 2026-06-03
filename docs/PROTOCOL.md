# Architecture & BLE Protocol

How ARMY Light is built, the verified Bluetooth protocol it speaks, and the
discovery tools for confirming or extending device support.

---

## Architecture

A single Python package, `army_light/`, run as two threads bridged by
`asyncio.run_coroutine_threadsafe`:

- **Main / AppKit thread** runs the `rumps` menu-bar UI (`app.py`). AppKit owns
  the main runloop, so nothing blocking may run here. A `rumps.Timer` polls the
  controller's status into the menu — no cross-thread UI calls.
- **Background thread** runs `WandController`'s private `asyncio` loop
  (`controller.py`), where all `bleak` BLE work happens.

```
[menu click] --run_coroutine_threadsafe--> [asyncio loop] --bleak--> [wand]
  main thread                               background thread          BLE
```

**Connection model.** The wand idle-disconnects, so there is no persistent link.
Each color write resolves the wand (preferring the advertised **service UUID**,
falling back to a name substring), connects if needed, writes, and drops the
client on failure so the next click reconnects. An `asyncio.Lock` serializes
writes so overlapping clicks can't race the connection. On connect the controller
optionally subscribes to notifications and sends a white "wake" packet, mimicking
the official app for link stability.

**Module map**

| Module | Responsibility |
|---|---|
| `config.py` | `Settings` dataclass + JSON persistence; macOS file locations |
| `packets.py` | Pluggable packet-format registry + non-color query packets |
| `palette.py` | Menu colors + `parse_color()` |
| `controller.py` | BLE link: resolve / connect / write / reconnect |
| `discovery.py` | `scan` / `inspect` / `probe` / `monitor` |
| `cli.py` | argparse dispatch (app vs. discovery subcommands) |
| `app.py` | rumps menu-bar UI |

---

## The protocol (verified — ARMY Bomb Ver. 4)

Verified **on a real BTS ARMY Bomb Ver. 4** (advertised name `BTS_V4 LS`,
manufacturer Elcomtec, Telink BLE SoC) on 2026-06-03, end-to-end from this app.
The V4 is **not** on the Fanlight platform — its GATT is a custom Elcomtec layout,
independently corroborated by
[ryanDonsi/Light-Stick-SDK](https://github.com/ryanDonsi/Light-Stick-SDK)
(the only public source matching this GATT). There is **no auth/handshake** for
color control.

| Field | Value |
|---|---|
| Advertised name | `BTS_V4 LS` — **no service UUIDs in the advertisement**, so the wand is resolved by name substring (`BTS`) |
| LED control service | `0001fe01-0000-1000-8000-00805f9800c4` (custom base `…00805f9800c4`) |
| Color characteristic | `0001ff01-0000-1000-8000-00805f9800c4` (read/write) |
| Commit characteristic | `0001ff13-0000-1000-8000-00805f9800c4` (write-without-response) |
| Write type | color: **with**-response (ff01 accepts nothing else — CoreBluetooth silently drops no-response writes to it); commit: without-response |

**Color control** (`bts_v4` format, 4 bytes `RR GG BB TT`, TT = transition/fade
in 10ms units, no header/checksum) — with one twist, established empirically:

- A write of `01` to `ff13` makes the wand **apply the pending color and restart
  its BLE session**: it leaves the power-on blinking-blue pairing animation AND
  **drops the link ~1-2s later**. It is *not* a per-write commit.
- So each fresh connection is **latched once**: `ff01 <- color`, `ff13 <- 01`,
  accept the drop, reconnect. After that, plain `ff01` writes apply **instantly
  over a persistent, stable link** (verified: 8 writes + 20s idle, no drop) —
  no further `ff13`, which would just drop the link again.
- Committing after every write (the obvious reading) reconnect-storms the wand —
  60+ connect cycles can wedge its BLE stack until a power cycle.

`ff13` is the one piece the Light-Stick-SDK doesn't document. Other V4 chars:
`ff02` 20-byte effect payload per the SDK, but **guarded on this firmware**
(no-response writes are ignored; with-response writes to `ff02`/`ff04` crash the
link) — so effects are app-driven over `ff01`. `ff05` internal MAC, plus standard
Device Information and Battery services.

These are the defaults in `config.py` / `packets.py`. The registry keeps
`fanlight` (the protocol of sibling Fanlight-platform sticks — service
`…0d1911`, char `…0d2b19`, packet `01 01 0B 00 00 RR GG BB 00 00 CK` with
`CK = (0x0B+R+G+B) & 0xFF`) and the generic `triones` / `elk_bledom` / `raw_rgb`
formats as `probe` fallbacks for other hardware.

Sources: this repo's `probe`/`inspect` session against a real V4 unit;
[ryanDonsi/Light-Stick-SDK](https://github.com/ryanDonsi/Light-Stick-SDK) (GATT map,
4-byte color packet);
[TR0U8L3-gif/kpop-lightsticks](https://github.com/TR0U8L3-gif/kpop-lightsticks) and
[gengkev/kpop-lightstick-experiments](https://github.com/gengkev/kpop-lightstick-experiments)
(Fanlight family).

---

## Verifying / extending support on your wand

If a color doesn't work — or you have a different ARMY Bomb version — the
discovery CLI confirms the real values. Run with the wand on, in Bluetooth mode,
unpaired from the phone. (`army-light <cmd>` after `pip install -e .`, or
`python -m army_light <cmd>`.)

**1. Scan** — find the wand:

```bash
army-light scan
```

A Ver. 4 shows up as `BTS_V4 LS` (it advertises no service UUIDs). Note the
address — on macOS it's a per-Mac CoreBluetooth UUID, not a hardware MAC, so the
app re-resolves by name/service at runtime rather than caching it.

**2. Inspect** — list characteristics:

```bash
army-light inspect <address>
```

Dumps every GATT service/characteristic and flags writable ones. On a Ver. 4 you
should see `0001ff01` (read/write) and `0001ff13` (write-without-response); on a
Fanlight-family stick, `…2b19` as `write-without-response,notify`.

**3. Probe** — confirm color control:

```bash
army-light probe <address>                 # target red, tries each format
army-light probe <address> --color green
```

It writes a candidate packet, then asks whether the wand changed. On a match it
prints the exact values and a `set-config` command. To go straight at the
known-good V4 combo:

```bash
army-light probe <address> --char 0001ff01-0000-1000-8000-00805f9800c4 --format bts_v4
```

(Note: on a V4 a bare `probe` color write may not show until a commit byte is
written — the app does this automatically via `commit_char_uuid`.)

**4. Save** verified values (only if `probe` found a different combo):

```bash
army-light set-config --char <uuid> --commit-char <uuid|''> --format <name> --response <true|false>
```

**5. Monitor** — only if nothing works, to watch for an unexpected handshake:

```bash
army-light monitor <address>
```

### Confirming with a capture (definitive)

To verify the exact bytes for a specific unit: enable **Bluetooth HCI snoop log**
on Android, drive the official app through known colors, pull
`btsnoop_hci.log`, and open it in Wireshark. Filter on ATT writes — you should see
`Write Command (0x52)` packets like `01 01 0b 00 00 ff 00 00 00 00 0a` (red) to the
`…2b19` characteristic.

---

## Roadmap

The current build is a manual color changer. Planned next phase: a notification
source (Gmail/IMAP poll → color rules), an idle/resting color, and a timed alert
color that returns to idle. The connect/write layer carries over unchanged.

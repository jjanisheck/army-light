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

## The protocol (verified — Fanlight family)

The official BTS app (`bts.kr.co.fanlight.fanlightapp`) is built on the shared
**Fanlight** platform used by many official K-pop lightsticks. The BLE color
protocol below is confirmed from decompiled official source plus two independent
working clients (one of them Python + `bleak` on macOS) — verified against sibling
sticks (P1Harmony, LOONA/Loossemble). It is **not yet confirmed against a BTS unit
specifically**, which is what `probe` is for. There is **no auth/handshake** for
color control in Self Mode.

| Field | Value |
|---|---|
| Service UUID | `00010203-0405-0607-0809-0a0b0c0d1911` (used to find the wand) |
| Write / notify characteristic | `00010203-0405-0607-0809-0a0b0c0d2b19` |
| Write type | write-**without**-response (retry with-response on failure) |

**Color packet** (`fanlight` format, 11 bytes):

```
01 01 0B 00 00 RR GG BB 00 00 CK
                                ^ checksum = (sum of bytes[2..9]) & 0xFF
                                           = (0x0B + R + G + B) & 0xFF
```

Examples: red `01 01 0b 00 00 ff 00 00 00 00 0a`, white
`01 01 0b 00 00 ff ff ff 00 00 08`, off `01 01 0b 00 00 00 00 00 00 00 0b`.
There's no brightness opcode — the app bakes brightness into RGB. Non-color query
packets (`01 01 06 50 XX CK`) for battery/firmware/hardware live in `packets.py`.

These are the defaults in `config.py` / `packets.py` — no longer guesses. The
other registry formats (`triones`, `elk_bledom`, `raw_rgb`) remain only as `probe`
fallbacks for unexpected firmware.

Sources: [TR0U8L3-gif/kpop-lightsticks](https://github.com/TR0U8L3-gif/kpop-lightsticks)
(decompiled official app + dev vlog),
[gengkev/kpop-lightstick-experiments](https://github.com/gengkev/kpop-lightstick-experiments)
(bleak/macOS + Web Bluetooth, confirmed working).

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

Look for the line flagged `<-- looks like the wand (Fanlight service)`, which
matches the service UUID regardless of the advertised name (the BTS name isn't
publicly documented). Note the address — on macOS it's a per-Mac CoreBluetooth
UUID, not a hardware MAC, so we resolve by service UUID at runtime rather than
caching it.

**2. Inspect** — list characteristics:

```bash
army-light inspect <address>
```

Dumps every GATT service/characteristic and flags writable ones. You should see
`…2b19` as `write-without-response,notify`.

**3. Probe** — confirm color control:

```bash
army-light probe <address>                 # target red, tries each format
army-light probe <address> --color green
```

It writes a candidate packet, then asks whether the wand changed. On a match it
prints the exact values and a `set-config` command. To go straight at the
known-good combo:

```bash
army-light probe <address> --char 00010203-0405-0607-0809-0a0b0c0d2b19 --format fanlight
```

**4. Save** verified values (only if `probe` found a different combo):

```bash
army-light set-config --char <uuid> --format <name> --response <true|false>
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

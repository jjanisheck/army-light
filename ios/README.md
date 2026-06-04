# ARMY Light for iOS

A native SwiftUI iPhone/iPad app that drives a BTS ARMY Bomb **Ver. 4** over
Bluetooth LE — the iOS sibling of the macOS panel app in the repo root, with
the same design and feature set:

- **Glowing hero wand** preview mirroring the live color/brightness/effect
- **3×7 color grid** — the seven members in their signature colors with
  initials (RM/JIN/SUGA/J-HOPE/JIMIN/V/JK) plus 14 spectrum colors, sent
  LED-true (fully saturated hues, no washed-out whites)
- **11 app-driven effects** in Ambient / High-energy groups — Blink, Breath,
  Strobe, Duo Fade, Color Cycle, Rainbow, Glow Cycle, Candle, Party, Jungle,
  Ice — tap an active effect (or Stop) to clear it
- **Brightness slider** (software RGB scaling) and a custom color picker
- Foreground **rules** that flash an alert color and return to idle

The BLE protocol and effects engine are faithful, **byte-identical** ports of
the Python package (`army_light/`), which remains the source-of-truth.

## Requirements

- Xcode 16+ (developed against Xcode 26.1, Swift 6.2 toolchain, Swift 5 language mode)
- iOS 17.0+ device with Bluetooth (the **Simulator has no Bluetooth**, so BLE
  can only be exercised on a real device; the Simulator runs the UI and tests)

## Build & run

Open the project and run on a device:

```bash
open ios/ArmyLight.xcodeproj
# Select your iPhone, set a signing Team (Signing & Capabilities), ⌘R
```

Or from the command line (Simulator — UI + unit tests only, no BLE):

```bash
cd ios
xcodebuild build -scheme ArmyLight -sdk iphonesimulator \
  -destination 'platform=iOS Simulator,name=iPhone 17'
xcodebuild test  -scheme ArmyLight -sdk iphonesimulator \
  -destination 'platform=iOS Simulator,name=iPhone 17'
```

## Project layout

```
ios/
├── ArmyLight.xcodeproj/        # hand-written; uses file-system-synchronized
│                               # groups, so new files in ArmyLight/ are picked
│                               # up automatically (no pbxproj edits needed)
├── ArmyLight/
│   ├── App/                    # @main entry + 3-tab root view
│   ├── Protocol/               # Packets.swift, Palette.swift (port of Python)
│   ├── BLE/                    # BLEEngine (CoreBluetooth) + WandController
│   ├── Rules/                  # ColorRule + RulesEngine (idle/alert hold)
│   ├── Settings/               # AppSettings (@Observable, UserDefaults-backed)
│   ├── Views/                  # Control / Rules / Settings screens
│   └── Assets.xcassets/        # AppIcon (placeholder), AccentColor
└── ArmyLightTests/             # XCTest: packets, palette, rules engine
```

## Architecture

- **`BLEEngine`** — low-level CoreBluetooth wrapped in async/await. All CB state
  is confined to one private serial queue; each delegate callback resumes a
  parked `Void` continuation (with a per-op timeout work item), so every async
  call resolves exactly once.
- **`WandController`** (`@MainActor @Observable`) — the policy layer, mirroring
  the Python `controller.py`: each fresh connection is **latched once** (write
  the requested color + the ff13 session-restart byte, let the wand drop the
  link, reconnect), then plain color writes stream over a persistent link.
  Failures drop the client so the next call reconnects and re-latches. Writes
  are serialized. UI reads `state` / `lastError` / `lastRGB`.
- **`RulesEngine`** (`@MainActor @Observable`) — holds the rule list (persisted as
  JSON in UserDefaults) and the idle/alert-hold behavior. **Foreground only** —
  iOS gives no reliable background BLE guarantees, so rules evaluate while the app
  is open (tap *Simulate* to fire one).

## Verified protocol — ARMY Bomb Ver. 4 (see `docs/PROTOCOL.md`)

- Advertised name `BTS_V4 LS`, **no service UUIDs in the advertisement** — the
  scan is unfiltered and matches by name substring (`BTS`); LED service
  `0001fe01-0000-1000-8000-00805f9800c4` (helps retrieve connected peripherals)
- Color char `0001ff01-…-00805f9800c4`: `bts_v4` packet = 4 bytes
  `RR GG BB TT` (TT = fade in 10ms units), write **with**-response only
- Latch char `0001ff13-…-00805f9800c4`: `01` once per fresh connection — the
  wand applies the color, exits its pairing animation, and restarts its BLE
  session (drops the link); never write it per color
- No auth. `fanlight` (`…0d1911`/`…0d2b19`, checksummed 11-byte packet) and the
  generic formats remain as fallbacks; stored pre-V4 settings migrate forward
  automatically (`AppSettings.protocolVersion`)

The wand must be **unpaired from the phone app** and its switch set to Bluetooth
mode — only one host can own the BLE link at a time.

## TestFlight / App Store

1. Set your **Team** and a unique bundle ID under *Signing & Capabilities*
   (default `com.example.armylight`).
2. `Product ▸ Archive`, then distribute via the Organizer to App Store Connect.
3. The Bluetooth usage string (`NSBluetoothAlwaysUsageDescription`) is generated
   into the Info.plist from build settings — App Review requires it, and it's
   already populated.

There are no background modes declared (the app is foreground-only by design),
which keeps the privacy/review story simple.

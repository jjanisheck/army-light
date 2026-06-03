# ARMY Light for iOS

A native SwiftUI iPhone/iPad app that drives a BTS ARMY Bomb lightstick to
arbitrary RGB colors over Bluetooth LE — the iOS sibling of the macOS menu-bar
app in the repo root. Tap a color, the wand changes. Set up foreground "rules"
that flash an alert color and return to a resting/idle color after a hold.

The BLE protocol is a faithful, **byte-identical** port of the Python package
(`army_light/`), which remains the protocol source-of-truth.

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
  the Python `controller.py`: no persistent connection (the wand
  idle-disconnects), so each color write resolves → connects → optionally sends a
  white "wake" packet → writes, dropping the link on failure so the next call
  reconnects. Writes are serialized. UI reads `state` / `lastError` / `lastRGB`.
- **`RulesEngine`** (`@MainActor @Observable`) — holds the rule list (persisted as
  JSON in UserDefaults) and the idle/alert-hold behavior. **Foreground only** —
  iOS gives no reliable background BLE guarantees, so rules evaluate while the app
  is open (tap *Simulate* to fire one).

## Verified protocol (from the repo root `CLAUDE.md` / `docs/PROTOCOL.md`)

- Service UUID `00010203-0405-0607-0809-0a0b0c0d1911` (used to resolve the wand)
- Write/notify char `00010203-0405-0607-0809-0a0b0c0d2b19`
- `fanlight` color packet: `01 01 0B 00 00 RR GG BB 00 00 CK`,
  `CK = (0x0B + R + G + B) & 0xFF`
- Write-without-response (retry with-response on failure); no auth for color

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

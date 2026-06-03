# ARMY Light — Stream Deck plugin

Control the wand from Stream Deck keys: **every color, effect, and brightness
preset from the Mac app as a ready-made, pre-colored action** — 39 in total.

| Group | Actions |
|---|---|
| Colors (16) | Red, Orange, Amber, Yellow, Lime, Green, Mint, Cyan, Sky, Blue, **ARMY Purple**, Purple, Magenta, Pink, Rose, White — each key renders the actual color swatch |
| Effects (11) | Blink, Breath, Strobe, Duo Fade, Color Cycle, Rainbow, Glow Cycle, Candle, Party, Jungle, Ice — themed key icons |
| Brightness (5) | 10% / 25% / 50% / 75% / 100% — keys show a fill gauge |
| Commands (3) | Off, Stop Effect, Reconnect |
| Custom (4) | Custom Color (full RGB picker), Custom Effect (per-effect color pickers), Custom Brightness (any percent), Custom Command |

## Requirements

- The **ARMY Light app must be running** on the same Mac (the plugin talks to
  its localhost remote, `http://127.0.0.1:8722` — see the main README).
- Stream Deck software 6.0+ on macOS 12+.

## Install

From the repo root:

```bash
cp -R streamdeck/com.armylight.control.sdPlugin \
  ~/Library/Application\ Support/com.elgato.StreamDeck/Plugins/
killall "Stream Deck"; open -a "Elgato Stream Deck"
```

That's it — no build step, no dependencies. In the Stream Deck app you'll now
have an **ARMY Light** category in the actions list (purple icon, right-hand
panel).

## Use

1. Drag any action onto a key — e.g. "ARMY Purple", "Rainbow", "Brightness 50%",
   "Off". Ready-made actions need **zero configuration**; the key icon shows
   the color/theme.
2. Press the key. ✓ flashes on success; ⚠ means the ARMY Light app isn't
   running (or the wand needs the panel's Reconnect).
3. The four **Custom …** actions have an inspector panel: a native color picker
   for any RGB value, per-effect color choices (e.g. Duo Fade between any two
   colors), any brightness percent, and a port override if you changed
   `control_port` in the app's config.

Tip: a 4×4 page of color keys plus a row of effects makes a great light board.
All actions work in Multi Actions too (e.g. "Blue, then Strobe" on one key).

## Uninstall

Delete the plugin folder and restart Stream Deck:

```bash
rm -rf ~/Library/Application\ Support/com.elgato.StreamDeck/Plugins/com.armylight.control.sdPlugin
killall "Stream Deck"; open -a "Elgato Stream Deck"
```

## Development

The manifest and all icons are **generated from the app's own palette and
effects registries** so the deck never drifts from the app:

```bash
python streamdeck/generate.py   # regenerate manifest.json + images/
```

Add a color to `army_light/palette.py` or an effect to `army_light/effects.py`,
re-run the generator, re-copy the plugin, and the new key appears.

Layout: `manifest.json` (actions), `plugin.js` (renders key icons on a canvas
and fires GETs at the localhost remote), `pi/*.html` (inspector panels for the
Custom actions), `images/` (generated icons).

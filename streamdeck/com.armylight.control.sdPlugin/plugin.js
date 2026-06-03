/* ARMY Light — Stream Deck plugin backend.
 *
 * Talks to the ARMY Light macOS app's localhost remote (default port 8722).
 * Keys render their own icons on a canvas: color keys as swatches of the
 * configured color, effect keys as themed thumbnails, so the deck mirrors
 * what the wand will do.
 *
 * Palette/effect lists mirror army_light/palette.py and effects.py.
 */

"use strict";

const DEFAULT_PORT = 8722;

// label -> [r, g, b]  (mirror of army_light/palette.py PALETTE, minus Off)
const PALETTE = {
  "Red": [255, 0, 0], "Orange": [255, 80, 0], "Amber": [255, 150, 0],
  "Yellow": [255, 210, 0], "Lime": [160, 255, 0], "Green": [0, 255, 0],
  "Mint": [0, 255, 150], "Cyan": [0, 200, 255], "Sky": [80, 140, 255],
  "Blue": [0, 0, 255], "ARMY Purple": [130, 60, 255], "Purple": [160, 0, 255],
  "Magenta": [255, 0, 255], "Pink": [255, 40, 150], "Rose": [255, 120, 170],
  "White": [255, 255, 255],
};

// label -> colors the effect takes (mirror of army_light/effects.py EFFECTS)
const EFFECTS = {
  "Blink": 1, "Breath": 1, "Strobe": 1, "Duo Fade": 2,
  "Color Cycle": 0, "Rainbow": 0, "Glow Cycle": 0,
  "Candle": 0, "Party": 0, "Jungle": 0, "Ice": 0,
};

let ws = null;
const contexts = {};  // context -> {action, settings}

/* ---- preset actions ------------------------------------------------------ */
/* Ready-made keys (com.armylight.preset.*) are fixed variants of the four
 * configurable actions: their settings are baked into the UUID. */

const SLUG_TO_COLOR = {};
Object.keys(PALETTE).forEach((n) => { SLUG_TO_COLOR[n.toLowerCase().replace(/ /g, "-")] = n; });
const SLUG_TO_EFFECT = {};
Object.keys(EFFECTS).forEach((n) => { SLUG_TO_EFFECT[n.toLowerCase().replace(/ /g, "-")] = n; });

function normalize(action, settings) {
  const m = action.match(/^com\.armylight\.preset\.(color|fx|bright|cmd)\.(.+)$/);
  if (!m) return { action, settings };
  const [, kind, slug] = m;
  if (kind === "color") {
    return { action: "com.armylight.color",
             settings: { colorMode: "palette", paletteColor: SLUG_TO_COLOR[slug] || "ARMY Purple" } };
  }
  if (kind === "fx") {
    return { action: "com.armylight.effect",
             settings: { effect: SLUG_TO_EFFECT[slug] || "Rainbow" } };
  }
  if (kind === "bright") {
    return { action: "com.armylight.brightness", settings: { percent: Number(slug) } };
  }
  return { action: "com.armylight.command", settings: { command: slug } };
}

/* ---- Stream Deck wiring ------------------------------------------------- */

function connectElgatoStreamDeckSocket(inPort, inPluginUUID, inRegisterEvent) {
  ws = new WebSocket("ws://127.0.0.1:" + inPort);
  ws.onopen = () => ws.send(JSON.stringify({ event: inRegisterEvent, uuid: inPluginUUID }));
  ws.onmessage = (msg) => {
    const e = JSON.parse(msg.data);
    const ctx = e.context;
    if (e.event === "willAppear" || e.event === "didReceiveSettings") {
      contexts[ctx] = normalize(e.action, (e.payload && e.payload.settings) || {});
      renderKey(ctx);
    } else if (e.event === "willDisappear") {
      delete contexts[ctx];
    } else if (e.event === "keyDown") {
      fire(ctx);
    }
  };
}

function sd(event, context, payload) {
  ws.send(JSON.stringify({ event, context, payload }));
}

/* ---- firing requests ----------------------------------------------------- */

function urlFor(entry) {
  const s = entry.settings;
  const port = s.port || DEFAULT_PORT;
  const base = "http://127.0.0.1:" + port;
  if (entry.action === "com.armylight.color") {
    const hex = colorHex(s).slice(1);
    return base + "/color/" + hex;
  }
  if (entry.action === "com.armylight.effect") {
    const label = s.effect || "Rainbow";
    let url = base + "/effect/" + encodeURIComponent(label.toLowerCase().replace(/ /g, "-"));
    const arity = EFFECTS[label] || 0;
    if (arity >= 1) url += "?color=" + (s.color1 || "#823cff").slice(1);
    if (arity === 2) url += "&color2=" + (s.color2 || "#ff2896").slice(1);
    return url;
  }
  if (entry.action === "com.armylight.brightness") {
    return base + "/brightness/" + (s.percent != null ? s.percent : 100);
  }
  // command
  return base + "/" + (s.command || "off");
}

function fire(ctx) {
  const entry = contexts[ctx];
  if (!entry) return;
  fetch(urlFor(entry))
    .then((r) => (r.ok ? sd("showOk", ctx) : Promise.reject(r.status)))
    .catch(() => sd("showAlert", ctx));
}

/* ---- key rendering -------------------------------------------------------- */

function colorHex(settings) {
  if (settings.colorMode === "custom" && settings.customColor) return settings.customColor;
  const rgb = PALETTE[settings.paletteColor || "ARMY Purple"] || PALETTE["ARMY Purple"];
  return "#" + rgb.map((c) => c.toString(16).padStart(2, "0")).join("");
}

function roundRect(g, x, y, w, h, r) {
  g.beginPath();
  g.moveTo(x + r, y);
  g.arcTo(x + w, y, x + w, y + h, r);
  g.arcTo(x + w, y + h, x, y + h, r);
  g.arcTo(x, y + h, x, y, r);
  g.arcTo(x, y, x + w, y, r);
  g.closePath();
}

function makeCanvas() {
  const c = document.createElement("canvas");
  c.width = 144; c.height = 144;
  const g = c.getContext("2d");
  g.fillStyle = "#1d1d1f";
  g.fillRect(0, 0, 144, 144);
  return [c, g];
}

function label(g, text, y, size) {
  g.fillStyle = "#ffffff";
  g.font = "bold " + (size || 20) + "px -apple-system, Helvetica";
  g.textAlign = "center";
  g.shadowColor = "rgba(0,0,0,0.8)"; g.shadowBlur = 6;
  g.fillText(text, 72, y, 132);
  g.shadowBlur = 0;
}

const EFFECT_THEMES = {
  "Color Cycle": ["#ff0000", "#ffd200", "#00ff00", "#00c8ff", "#0000ff", "#ff00ff"],
  "Rainbow": ["#ff0000", "#ff5000", "#ffd200", "#00ff00", "#0000ff", "#4b0082", "#a000ff"],
  "Glow Cycle": ["#1a0030", "#a000ff", "#1a0030", "#00c8ff", "#1a0030"],
  "Candle": ["#ff9614", "#ffc850", "#b45a00"],
  "Party": ["#ff0040", "#00e0ff", "#ffe000", "#a000ff"],
  "Jungle": ["#0a7819", "#78dc28", "#d2a014", "#008c78"],
  "Ice": ["#a0dcff", "#5aaaff", "#ffffff", "#3c64dc"],
};

function renderKey(ctx) {
  const entry = contexts[ctx];
  if (!entry) return;
  const s = entry.settings;
  const [c, g] = makeCanvas();

  if (entry.action === "com.armylight.color") {
    g.fillStyle = colorHex(s);
    roundRect(g, 14, 14, 116, 116, 26);
    g.fill();
    if (s.showName !== false) {
      const name = s.colorMode === "custom" ? (s.customColor || "") :
        (s.paletteColor || "ARMY Purple");
      label(g, name, 132, 18);
    }
  } else if (entry.action === "com.armylight.effect") {
    const name = s.effect || "Rainbow";
    const arity = EFFECTS[name] || 0;
    const colors = arity >= 1
      ? (arity === 2 ? [s.color1 || "#823cff", s.color2 || "#ff2896"]
                     : [s.color1 || "#823cff", "#1d1d1f", s.color1 || "#823cff"])
      : (EFFECT_THEMES[name] || ["#823cff", "#ff2896"]);
    const grad = g.createLinearGradient(14, 14, 130, 130);
    colors.forEach((col, i) => grad.addColorStop(i / Math.max(colors.length - 1, 1), col));
    g.fillStyle = grad;
    roundRect(g, 14, 14, 116, 116, 26);
    g.fill();
    label(g, name, 80, 22);
  } else if (entry.action === "com.armylight.brightness") {
    const pct = s.percent != null ? s.percent : 100;
    g.fillStyle = "#3a3a3c";
    roundRect(g, 14, 14, 116, 116, 26); g.fill();
    g.fillStyle = "#ffd200";
    roundRect(g, 14, 14 + 116 * (1 - pct / 100), 116, 116 * (pct / 100), 12); g.fill();
    label(g, pct + "%", 84, 30);
  } else {
    const cmd = s.command || "off";
    const looks = { off: ["#2c2c2e", "OFF"], stop: ["#8e2c2c", "STOP"], reconnect: ["#2c5a8e", "RE-\nCONNECT"] };
    const [bg, text] = looks[cmd] || looks.off;
    g.fillStyle = bg;
    roundRect(g, 14, 14, 116, 116, 26); g.fill();
    const lines = text.split("\n");
    lines.forEach((t, i) => label(g, t, 76 + (i - (lines.length - 1) / 2) * 28, 24));
  }

  sd("setImage", ctx, { image: c.toDataURL("image/png"), target: 0 });
}

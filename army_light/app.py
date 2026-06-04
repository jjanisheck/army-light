"""The menu-bar app — a persistent overlay panel (daily-use mode).

Clicking the menu-bar icon toggles a floating panel that STAYS OPEN while you
click colors and effects (and while other apps have focus), until you click the
icon again. Built directly on AppKit via PyObjC (a rumps dependency, so nothing
new) because NSMenu always self-dismisses on click — a panel doesn't.

Visual design implemented from the Claude Design handoff (tasks/ bundle,
2026-06-04): premium dark popover, glowing hero wand, a 3x7 color grid whose
top row is the seven members in their signature colors with initials, grouped
effects, and a glowing brightness slider. Original fan design — intentionally
not the official ARMY BOMB branding.

Threading model is unchanged: all clicks hand work to WandController's
background asyncio loop; an NSTimer polls controller state back into the panel.
"""

from __future__ import annotations

import colorsys
import logging
import subprocess

import objc
from AppKit import (
    NSApplication,
    NSBackingStoreBuffered,
    NSBezierPath,
    NSButton,
    NSColor,
    NSFloatingWindowLevel,
    NSFont,
    NSFontAttributeName,
    NSForegroundColorAttributeName,
    NSGradient,
    NSMakeRect,
    NSMutableParagraphStyle,
    NSPanel,
    NSParagraphStyleAttributeName,
    NSSlider,
    NSStatusBar,
    NSTextField,
    NSVariableStatusItemLength,
    NSView,
    NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSWindowStyleMaskBorderless,
    NSWindowStyleMaskNonactivatingPanel,
)
from Foundation import NSAttributedString, NSObject, NSTimer

from . import APP_NAME, config
from .controller import WandController
from .effects import EFFECTS

log = logging.getLogger(__name__)

# Menu-bar icon: a purple heart — solid when the light is on, outline when off.
HEART_SOLID = "♥"
HEART_OUTLINE = "♡"
HEART_PURPLE = (154, 108, 255)


def _heart(solid):
    return _attr(HEART_SOLID if solid else HEART_OUTLINE, 15, _ns(HEART_PURPLE))

# ---- design tokens (from the handoff's app.css / app.jsx) --------------------
WIDTH = 452
PAD = 20
GAP = 11
RADIUS = 16
ACCENT = (200, 155, 255)          # #c89bff
BG = (18, 18, 23)                  # popover body
CARD = (255, 255, 255, 0.05)       # fx/tool button fill
CARD_BORDER = (255, 255, 255, 0.08)
GREEN = (69, 224, 138)             # connection dot ok
RED = (255, 97, 97)                # connection dot off

# Top row: the seven members in their signature colors (+ initial text color).
MEMBERS = [
    ("RM", (43, 127, 255), (255, 255, 255)),
    ("JIN", (255, 143, 200), (58, 16, 32)),
    ("SUGA", (27, 27, 32), (255, 255, 255)),
    ("J-HOPE", (255, 59, 59), (255, 255, 255)),
    ("JIMIN", (255, 200, 61), (58, 44, 0)),
    ("V", (54, 200, 113), (6, 33, 15)),
    ("JK", (154, 108, 255), (255, 255, 255)),
]

# Two rows of general colors below the member row (full ROYGBIV spread).
EXTRA_COLORS = [
    (255, 77, 77), (255, 122, 26), (255, 176, 32), (255, 227, 77),
    (182, 240, 60), (63, 214, 107), (45, 224, 192),
    (51, 199, 255), (59, 130, 246), (108, 92, 231), (168, 85, 247),
    (233, 79, 208), (255, 111, 165), (255, 255, 255),
]

FX_GROUPS = [
    ("AMBIENT", ["Breath", "Candle", "Ice", "Color Cycle", "Rainbow", "Glow Cycle"]),
    ("HIGH ENERGY", ["Blink", "Strobe", "Duo Fade", "Party", "Jungle"]),
]

DEFAULT_EFFECT_RGB = (154, 108, 255)
DEFAULT_DUO_RGB = (255, 143, 200)


def _ns(rgb, a=1.0):
    return NSColor.colorWithSRGBRed_green_blue_alpha_(rgb[0] / 255, rgb[1] / 255, rgb[2] / 255, a)


def led_rgb(rgb):
    """Map a screen swatch color to an LED-true color.

    The design palette uses screen-pretty pastels (e.g. Red = #FF4D4D), but on
    the wand the embedded white component renders as a pink/washed glow with a
    white pool at the diffuser base. Fully saturate colorful picks (same hue),
    keep whites/blacks/grays neutral."""
    h, s, v = colorsys.rgb_to_hsv(rgb[0] / 255, rgb[1] / 255, rgb[2] / 255)
    if s >= 0.25:
        s = 1.0      # colorful pick → pure hue, no white contamination
    elif s <= 0.12:
        s = 0.0      # white / black / gray → keep neutral
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return (round(r * 255), round(g * 255), round(b * 255))


def _attr(text, size, color, bold=False, align="center"):
    para = NSMutableParagraphStyle.alloc().init()
    para.setAlignment_({"left": 0, "center": 1, "right": 2}[align])
    font = NSFont.boldSystemFontOfSize_(size) if bold else NSFont.systemFontOfSize_(size)
    return NSAttributedString.alloc().initWithString_attributes_(text, {
        NSFontAttributeName: font,
        NSForegroundColorAttributeName: color,
        NSParagraphStyleAttributeName: para,
    })


class FlippedView(NSView):
    def isFlipped(self):  # noqa: N802 (ObjC selector)
        return True


class FlatButton(NSButton):
    """A button that draws ONLY a flat rounded fill + its attributed title.

    macOS draws a glassy white bezel material under borderless NSButtons,
    which bleeds white into colored swatches — so suppress the cell's drawing
    entirely and paint the fill ourselves (solid colors, by hand)."""

    def initWithFrame_(self, frame):  # noqa: N802
        self = objc.super(FlatButton, self).initWithFrame_(frame)
        if self is None:
            return None
        self.fill = None      # NSColor or None
        self.radius = 10.0
        self.setBordered_(False)
        self.setTitle_("")
        return self

    def acceptsFirstMouse_(self, _event):  # noqa: N802
        return True

    @objc.python_method
    def set_fill(self, color):
        self.fill = color
        self.setNeedsDisplay_(True)

    def drawRect_(self, _rect):  # noqa: N802
        b = self.bounds()
        if self.fill is not None:
            path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(b, self.radius, self.radius)
            self.fill.setFill()
            path.fill()
            if self.cell().isHighlighted():
                NSColor.colorWithSRGBRed_green_blue_alpha_(0, 0, 0, 0.25).setFill()
                path.fill()
        title = self.attributedTitle()
        if title and title.length():
            size = title.size()
            title.drawInRect_(NSMakeRect(0, (b.size.height - size.height) / 2,
                                         b.size.width, size.height))


class FirstMouseSlider(NSSlider):
    """NSSlider ignores the first click in a non-activating panel (unlike
    NSButton, it doesn't accept 'first mouse'), leaving the knob inert. Accept
    it so the slider tracks drags without the panel being key."""

    def acceptsFirstMouse_(self, _event):  # noqa: N802
        return True


class WandView(NSView):
    """The glowing hero wand: glass sphere on a dark handle, lit by the
    current color, glow scaled by brightness (from the handoff's wand.jsx)."""

    def initWithFrame_(self, frame):  # noqa: N802
        self = objc.super(WandView, self).initWithFrame_(frame)
        if self is None:
            return None
        self.rgb = (154, 108, 255)
        self.glow = 1.0  # brightness 0..1; 0 = off
        return self

    @objc.python_method
    def set_state(self, rgb, glow):
        if (rgb, glow) != (self.rgb, self.glow):
            self.rgb = rgb
            self.glow = glow
            self.setNeedsDisplay_(True)

    def drawRect_(self, _rect):  # noqa: N802
        b = self.bounds()
        w, h = b.size.width, b.size.height
        sphere = min(h * 0.72, w * 0.4)
        cx = w / 2
        sphere_cy = h - sphere / 2 - 2          # sphere at the top (y-up coords)
        glow = max(0.06, self.glow)

        # handle (below the sphere, slightly overlapped)
        hw, hh = sphere * 0.30, sphere * 0.58
        handle = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            NSMakeRect(cx - hw / 2, sphere_cy - sphere / 2 - hh + sphere * 0.10, hw, hh), 7, 7)
        NSGradient.alloc().initWithColors_([
            _ns((5, 5, 6)), _ns((74, 74, 82)), _ns((42, 42, 48)), _ns((5, 5, 6)),
        ]).drawInBezierPath_angle_(handle, 0)
        # glowing accent ring on the handle
        ring = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            NSMakeRect(cx - hw * 0.28, sphere_cy - sphere / 2 + sphere * 0.02, hw * 0.56, 4), 2, 2)
        _ns(self.rgb, 0.25 + glow * 0.7).setFill()
        ring.fill()

        def circle(cx_, cy_, d):
            return NSBezierPath.bezierPathWithOvalInRect_(NSMakeRect(cx_ - d / 2, cy_ - d / 2, d, d))

        # outer aura
        aura = circle(cx, sphere_cy, sphere * 1.45)
        NSGradient.alloc().initWithColors_([_ns(self.rgb, glow * 0.40), _ns(self.rgb, 0.0)]) \
            .drawInBezierPath_relativeCenterPosition_(aura, (0, 0))
        # glass sphere base
        base = circle(cx, sphere_cy, sphere)
        NSGradient.alloc().initWithColors_([_ns((34, 34, 41)), _ns((11, 11, 14))]) \
            .drawInBezierPath_relativeCenterPosition_(base, (-0.25, 0.3))
        # colored core
        core = circle(cx, sphere_cy, sphere * 0.84)
        NSGradient.alloc().initWithColors_([
            _ns(self.rgb, min(1.0, 0.25 + glow * 0.9)), _ns(self.rgb, 0.0),
        ]).drawInBezierPath_relativeCenterPosition_(core, (0, 0))
        # emblem: soft bar + orb outline (original, abstract)
        bar = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            NSMakeRect(cx - sphere * 0.06, sphere_cy - sphere * 0.23, sphere * 0.12, sphere * 0.46),
            sphere * 0.05, sphere * 0.05)
        _ns((255, 255, 255), 0.35 + glow * 0.4).setFill()
        bar.fill()
        orb = circle(cx, sphere_cy, sphere * 0.26)
        orb.setLineWidth_(2)
        _ns((255, 255, 255), 0.3 + glow * 0.35).setStroke()
        orb.stroke()
        # gloss highlight
        gloss = NSBezierPath.bezierPathWithOvalInRect_(NSMakeRect(
            cx - sphere * 0.34, sphere_cy + sphere * 0.13, sphere * 0.40, sphere * 0.27))
        NSGradient.alloc().initWithColors_([_ns((255, 255, 255), 0.55), _ns((255, 255, 255), 0.0)]) \
            .drawInBezierPath_relativeCenterPosition_(gloss, (0, 0.2))
        # rim
        rim = circle(cx, sphere_cy, sphere)
        rim.setLineWidth_(1.5)
        _ns((255, 255, 255), 0.10).setStroke()
        rim.stroke()


class PanelApp(NSObject):
    """Status item + floating panel. Lives on the main/AppKit thread."""

    def initWithSettings_(self, settings):  # noqa: N802
        self = objc.super(PanelApp, self).init()
        if self is None:
            return None
        self.settings = settings
        self.controller = WandController(settings)
        self.controller.start()
        self._selected_rgb = None
        self._recent_rgbs = []   # last two distinct picks (Duo Fade's pair)
        self._swatches = []      # (button, rgb)
        self._fx_buttons = {}    # label -> button
        self._build_status_item()
        self._build_panel()
        self._server = None
        if settings.control_port:
            try:
                from .server import ControlServer
                self._server = ControlServer(self.controller, settings.control_port)
                self._server.start()
            except OSError as e:
                log.error("Control server failed to start: %s", e)
        self._timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            1.0, self, "refresh:", None, True
        )
        return self

    # ---- UI construction ------------------------------------------------------
    @objc.python_method
    def _build_status_item(self):
        self._item = NSStatusBar.systemStatusBar().statusItemWithLength_(NSVariableStatusItemLength)
        btn = self._item.button()
        btn.setAttributedTitle_(_heart(False))
        btn.setTarget_(self)
        btn.setAction_("togglePanel:")

    @objc.python_method
    def _label(self, text, y, size=11, bold=False, color=None, x=PAD, w=None, align="left"):
        lbl = NSTextField.labelWithString_(text)
        lbl.setAttributedStringValue_(_attr(text, size, color or _ns((242, 242, 245)), bold, align))
        lbl.setFrame_(NSMakeRect(x, y, w or (WIDTH - 2 * PAD), size + 8))
        self._content.addSubview_(lbl)
        return lbl

    @objc.python_method
    def _card_button(self, frame, action, radius=10, tag=0):
        b = FlatButton.alloc().initWithFrame_(frame)
        b.setTarget_(self)
        b.setAction_(action)
        b.setTag_(tag)
        b.radius = radius
        b.fill = _ns(CARD[:3], CARD[3])
        b.setWantsLayer_(True)
        layer = b.layer()
        layer.setCornerRadius_(radius)
        layer.setBorderWidth_(1)
        layer.setBorderColor_(_ns(CARD_BORDER[:3], CARD_BORDER[3]).CGColor())
        self._content.addSubview_(b)
        return b

    @objc.python_method
    def _section_label(self, text, y):
        self._label(text, y, size=11, bold=True, color=_ns((255, 255, 255), 0.42))

    @objc.python_method
    def _build_panel(self):
        sw = (WIDTH - 2 * PAD - 6 * GAP) / 7  # swatch side, 7 columns

        y = 18
        header_y, y = y, y + 44
        hero_y, y = y, y + 150
        meta_y, y = y, y + 36
        colors_lbl_y, y = y, y + 22
        grid_y, y = y, y + 3 * sw + 2 * GAP + 14
        fx_lbl_y, y = y, y + 22
        amb_cap_y, y = y, y + 17
        amb_y, y = y, y + 3 * 34 + 2 * 8 + 10
        high_cap_y, y = y, y + 17
        high_y, y = y, y + 3 * 34 + 2 * 8 + 12
        bright_lbl_y, y = y, y + 20
        slider_y, y = y, y + 28
        bar_y, y = y, y + 1 + 12
        tools_y, y = y, y + 36
        height = y + PAD - 4

        style = NSWindowStyleMaskBorderless | NSWindowStyleMaskNonactivatingPanel
        self._panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, WIDTH, height), style, NSBackingStoreBuffered, False
        )
        self._panel.setLevel_(NSFloatingWindowLevel)
        self._panel.setOpaque_(False)
        self._panel.setBackgroundColor_(NSColor.clearColor())
        self._panel.setHidesOnDeactivate_(False)
        self._panel.setBecomesKeyOnlyIfNeeded_(True)
        self._panel.setCollectionBehavior_(NSWindowCollectionBehaviorCanJoinAllSpaces)

        self._content = FlippedView.alloc().initWithFrame_(NSMakeRect(0, 0, WIDTH, height))
        self._content.setWantsLayer_(True)
        layer = self._content.layer()
        layer.setCornerRadius_(RADIUS)
        layer.setBackgroundColor_(_ns(BG, 0.97).CGColor())
        layer.setBorderWidth_(1)
        layer.setBorderColor_(_ns((255, 255, 255), 0.08).CGColor())
        self._panel.setContentView_(self._content)

        # ===== header: brand mark + name + connection, ghost Reconnect =====
        mark = NSView.alloc().initWithFrame_(NSMakeRect(PAD, header_y + 8, 12, 12))
        mark.setWantsLayer_(True)
        mark.layer().setBackgroundColor_(_ns(ACCENT).CGColor())
        mark.layer().setCornerRadius_(6)
        mark.layer().setShadowColor_(_ns(ACCENT).CGColor())
        mark.layer().setShadowOpacity_(0.9)
        mark.layer().setShadowRadius_(7)
        mark.layer().setShadowOffset_((0, 0))
        mark.layer().setMasksToBounds_(False)
        self._content.addSubview_(mark)
        self._label(APP_NAME, header_y - 2, size=16, bold=True, x=PAD + 23, w=220)
        self._conn_dot = NSView.alloc().initWithFrame_(NSMakeRect(PAD + 23, header_y + 25, 7, 7))
        self._conn_dot.setWantsLayer_(True)
        self._conn_dot.layer().setCornerRadius_(3.5)
        self._conn_dot.layer().setMasksToBounds_(False)
        self._content.addSubview_(self._conn_dot)
        self._status_label = self._label("Not connected", header_y + 19, size=11,
                                         color=_ns((255, 255, 255), 0.5), x=PAD + 35, w=230)
        self._connect_button = self._card_button(
            NSMakeRect(WIDTH - PAD - 96, header_y + 4, 96, 30), "reconnectClicked:", radius=9)
        self._connect_button.setAttributedTitle_(_attr("Reconnect", 12.5, _ns((255, 255, 255), 0.85)))

        # ===== hero wand =====
        self._wand = WandView.alloc().initWithFrame_(
            NSMakeRect(WIDTH / 2 - 90, hero_y, 180, 150))
        self._content.addSubview_(self._wand)
        self._hero_state = self._label("Solid color", meta_y, size=14, bold=True, align="center")
        self._hero_sub = self._label("100% brightness", meta_y + 19, size=11,
                                     color=_ns((255, 255, 255), 0.42), align="center")

        # ===== colors: 3 x 7 grid (members on top) =====
        self._section_label("COLORS", colors_lbl_y)
        for i, (name, rgb, text_rgb) in enumerate(MEMBERS):
            frame = NSMakeRect(PAD + i * (sw + GAP), grid_y, sw, sw)
            b = self._card_button(frame, "colorClicked:", radius=9, tag=i)
            b.fill = _ns(rgb)  # solid — FlatButton suppresses the white bezel
            b.layer().setBorderColor_(_ns((255, 255, 255), 0.10).CGColor())
            b.setAttributedTitle_(_attr(name, 9.5, _ns(text_rgb), bold=True))
            b.setToolTip_(name)
            self._swatches.append((b, rgb))
        for i, rgb in enumerate(EXTRA_COLORS):
            r, c = divmod(i + 7, 7)
            frame = NSMakeRect(PAD + c * (sw + GAP), grid_y + r * (sw + GAP), sw, sw)
            b = self._card_button(frame, "colorClicked:", radius=9, tag=i + 7)
            b.fill = _ns(rgb)
            b.layer().setBorderColor_(_ns((255, 255, 255), 0.07).CGColor())
            self._swatches.append((b, rgb))

        # ===== effects: grouped, with a Stop link =====
        self._section_label("EFFECTS", fx_lbl_y)
        stop = FlatButton.alloc().initWithFrame_(NSMakeRect(WIDTH - PAD - 50, fx_lbl_y - 3, 50, 20))
        stop.setAttributedTitle_(_attr("Stop", 12, _ns(ACCENT), bold=True, align="right"))
        stop.setTarget_(self)
        stop.setAction_("stopClicked:")
        self._content.addSubview_(stop)

        half = (WIDTH - 2 * PAD - GAP) / 2
        for cap_y, rows_y, (caption, labels) in ((amb_cap_y, amb_y, FX_GROUPS[0]),
                                                 (high_cap_y, high_y, FX_GROUPS[1])):
            self._label(caption, cap_y, size=10, color=_ns((255, 255, 255), 0.32))
            for i, label in enumerate(labels):
                r, c = divmod(i, 2)
                frame = NSMakeRect(PAD + c * (half + GAP), rows_y + r * (34 + 8), half, 34)
                b = self._card_button(frame, "effectClicked:", radius=10)
                b.setAttributedTitle_(self._fx_title(label, False))
                self._fx_buttons[label] = b

        # ===== brightness =====
        self._section_label("BRIGHTNESS", bright_lbl_y)
        self._label("☀", slider_y + 4, size=10, color=_ns((255, 255, 255), 0.4), w=16)
        self._slider = FirstMouseSlider.alloc().initWithFrame_(
            NSMakeRect(PAD + 22, slider_y, WIDTH - 2 * PAD - 78, 22))
        self._slider.setMinValue_(0.05)
        self._slider.setMaxValue_(1.0)
        self._slider.setDoubleValue_(1.0)
        self._slider.setContinuous_(True)
        self._slider.setTarget_(self)
        self._slider.setAction_("brightnessChanged:")
        self._content.addSubview_(self._slider)
        self._label("☀", slider_y + 1, size=15, color=_ns((255, 255, 255), 0.55),
                    x=WIDTH - PAD - 50, w=20)
        self._bval = self._label("100", slider_y + 3, size=12, color=_ns((255, 255, 255), 0.5),
                                 x=WIDTH - PAD - 30, w=30, align="right")

        # ===== toolbar =====
        bar = NSView.alloc().initWithFrame_(NSMakeRect(0, bar_y, WIDTH, 1))
        bar.setWantsLayer_(True)
        bar.layer().setBackgroundColor_(_ns((255, 255, 255), 0.05).CGColor())
        self._content.addSubview_(bar)
        quarter = (WIDTH - 2 * PAD - 3 * GAP) / 4
        for i, (title, action) in enumerate([("Off", "offClicked:"), ("Log", "logClicked:"),
                                             ("Config", "configClicked:"), ("Quit", "quitClicked:")]):
            b = self._card_button(
                NSMakeRect(PAD + i * (quarter + GAP), tools_y, quarter, 34), action)
            b.setAttributedTitle_(_attr(title, 13, _ns((255, 255, 255), 0.85)))

    @objc.python_method
    def _fx_title(self, label, active):
        dot = _ns(ACCENT) if active else _ns((255, 255, 255), 0.45)
        para = NSMutableParagraphStyle.alloc().init()
        para.setAlignment_(1)
        from Foundation import NSMutableAttributedString
        s = NSMutableAttributedString.alloc().init()
        s.appendAttributedString_(NSAttributedString.alloc().initWithString_attributes_(
            "● ", {NSFontAttributeName: NSFont.systemFontOfSize_(9),
                   NSForegroundColorAttributeName: dot, NSParagraphStyleAttributeName: para}))
        s.appendAttributedString_(NSAttributedString.alloc().initWithString_attributes_(
            label, {NSFontAttributeName: NSFont.systemFontOfSize_(13),
                    NSForegroundColorAttributeName: _ns((255, 255, 255), 0.95 if active else 0.88),
                    NSParagraphStyleAttributeName: para}))
        return s

    # ---- actions (ObjC selectors) ---------------------------------------------
    def togglePanel_(self, _sender):  # noqa: N802
        if self._panel.isVisible():
            self._panel.orderOut_(None)
            return
        btn = self._item.button()
        rect = btn.window().convertRectToScreen_(btn.convertRect_toView_(btn.bounds(), None))
        self._panel.setFrameTopLeftPoint_((rect.origin.x, rect.origin.y - 6))
        self._panel.orderFrontRegardless()

    def colorClicked_(self, sender):  # noqa: N802
        rgb = self._swatches[sender.tag()][1]
        self._select(rgb)
        if rgb in self._recent_rgbs:
            self._recent_rgbs.remove(rgb)
        self._recent_rgbs.append(rgb)
        del self._recent_rgbs[:-2]
        self.controller.set_color(led_rgb(rgb))

    def effectClicked_(self, sender):  # noqa: N802
        label = next((lbl for lbl, b in self._fx_buttons.items() if b is sender), None)
        if label is None:
            return
        if self.controller.current_effect == label:  # tap again to stop (design)
            self.controller.stop_effect()
            return
        arity = EFFECTS[label].arity
        if arity == 0:
            colors = None
        elif arity == 1:
            colors = led_rgb(self._selected_rgb or DEFAULT_EFFECT_RGB)
        else:
            pair = list(self._recent_rgbs)
            if len(pair) < 2:
                base = pair[0] if pair else DEFAULT_EFFECT_RGB
                other = DEFAULT_DUO_RGB if base != DEFAULT_DUO_RGB else DEFAULT_EFFECT_RGB
                pair = [base, other]
            colors = tuple(led_rgb(c) for c in pair)
        self.controller.start_effect(label, colors)

    def stopClicked_(self, _sender):  # noqa: N802
        self.controller.stop_effect()

    def reconnectClicked_(self, _sender):  # noqa: N802
        self._status_label.setAttributedStringValue_(
            _attr("Scanning…", 11, _ns((255, 255, 255), 0.5), align="left"))
        self.controller.reconnect()

    def offClicked_(self, _sender):  # noqa: N802
        self._select(None)
        self.controller.set_color((0, 0, 0))

    def logClicked_(self, _sender):  # noqa: N802
        subprocess.run(["open", str(config.log_path())], check=False)

    def configClicked_(self, _sender):  # noqa: N802
        subprocess.run(["open", str(config.config_path())], check=False)

    def quitClicked_(self, _sender):  # noqa: N802
        log.info("Quitting.")
        if self._server:
            self._server.stop()
        self.controller.shutdown()
        NSApplication.sharedApplication().terminate_(None)

    def brightnessChanged_(self, sender):  # noqa: N802
        value = float(sender.doubleValue())
        self._bval.setAttributedStringValue_(
            _attr(str(round(value * 100)), 12, _ns((255, 255, 255), 0.5), align="right"))
        self.controller.set_brightness(value)

    def refresh_(self, _timer):  # noqa: N802
        c = self.controller
        if c.connected:
            status, dot = "Connected · BTS v4", GREEN
        elif c.last_error:
            status, dot = c.last_error, RED
        else:
            status, dot = "Not connected — pick a color", RED
        # Solid purple heart while the light is on; outline when off/disconnected.
        # (During effects last_rgb passes through black, so an active effect
        # counts as "on" regardless of the current step.)
        lit = c.connected and (c.current_effect is not None
                               or (c.last_rgb is not None and c.last_rgb != (0, 0, 0)))
        self._item.button().setAttributedTitle_(_heart(lit))
        self._status_label.setAttributedStringValue_(
            _attr(status, 11, _ns((255, 255, 255), 0.5), align="left"))
        dl = self._conn_dot.layer()
        dl.setBackgroundColor_(_ns(dot).CGColor())
        dl.setShadowColor_(_ns(dot).CGColor())
        dl.setShadowOpacity_(0.9)
        dl.setShadowRadius_(5)
        dl.setShadowOffset_((0, 0))

        # hero wand + meta
        rgb = c.last_rgb or (154, 108, 255)
        off = c.last_rgb == (0, 0, 0)
        self._wand.set_state(rgb if not off else (20, 20, 24), 0.0 if off else c.brightness)
        state = "Off" if off else (c.current_effect or "Solid color")
        self._hero_state.setAttributedStringValue_(_attr(state, 14, _ns((242, 242, 245)), bold=True))
        self._hero_sub.setAttributedStringValue_(_attr(
            f"{round(c.brightness * 100)}% brightness", 11, _ns((255, 255, 255), 0.42)))

        # effect button states
        for label, b in self._fx_buttons.items():
            active = c.current_effect == label
            b.setAttributedTitle_(self._fx_title(label, active))
            border = _ns(ACCENT, 0.9) if active else _ns(CARD_BORDER[:3], CARD_BORDER[3])
            b.layer().setBorderColor_(border.CGColor())
            b.set_fill(_ns((255, 255, 255), 0.08 if active else CARD[3]))

    # ---- helpers ---------------------------------------------------------------
    @objc.python_method
    def _select(self, rgb):
        self._selected_rgb = rgb
        for b, srgb in self._swatches:
            selected = rgb is not None and srgb == rgb
            layer = b.layer()
            layer.setBorderWidth_(2 if selected else 1)
            layer.setBorderColor_((_ns(ACCENT) if selected else _ns((255, 255, 255), 0.08)).CGColor())
            layer.setMasksToBounds_(False)
            layer.setShadowColor_(_ns(srgb).CGColor())
            layer.setShadowOpacity_(0.8 if selected else 0.0)
            layer.setShadowRadius_(7)
            layer.setShadowOffset_((0, 0))


def run(settings: config.Settings) -> None:
    log.info("Starting %s panel app.", APP_NAME)
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(1)  # accessory: no Dock icon
    delegate = PanelApp.alloc().initWithSettings_(settings)
    assert delegate is not None
    app.run()

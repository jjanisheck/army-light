"""The menu-bar app — a persistent overlay panel (daily-use mode).

Clicking the menu-bar icon toggles a floating panel that STAYS OPEN while you
click colors and effects (and while other apps have focus), until you click the
icon again. Built directly on AppKit via PyObjC (a rumps dependency, so nothing
new) because NSMenu always self-dismisses on click — a panel doesn't.

Threading model is unchanged: all clicks hand work to WandController's
background asyncio loop; an NSTimer polls controller state back into the panel.
"""

from __future__ import annotations

import logging
import subprocess

import objc
from AppKit import (
    NSApplication,
    NSBackingStoreBuffered,
    NSButton,
    NSColor,
    NSFloatingWindowLevel,
    NSFont,
    NSImage,
    NSMakeRect,
    NSPanel,
    NSSlider,
    NSStatusBar,
    NSTextField,
    NSVariableStatusItemLength,
    NSView,
    NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSWindowStyleMaskBorderless,
    NSWindowStyleMaskNonactivatingPanel,
)
from Foundation import NSObject, NSTimer

from . import APP_NAME, config
from .controller import WandController
from .effects import EFFECTS
from .palette import PALETTE
from .server import ControlServer
from .swatches import swatch_path

log = logging.getLogger(__name__)

ICON_CONNECTED = "💡"
ICON_IDLE = "🔅"

# Panel layout (flipped view: y grows downward).
WIDTH = 280
MARGIN = 12
SWATCH = 26
COLS = 8
DEFAULT_EFFECT_RGB = (130, 60, 255)  # ARMY Purple, until a swatch is picked
DEFAULT_DUO_RGB = (255, 40, 150)     # Pink — Duo Fade's second color fallback

COLORS = [(label, rgb) for label, rgb in PALETTE if label != "Off"]


class FlippedView(NSView):
    def isFlipped(self):  # noqa: N802 (ObjC selector)
        return True


class FirstMouseSlider(NSSlider):
    """NSSlider ignores the first click in a non-activating panel (unlike
    NSButton, it doesn't accept 'first mouse'), leaving the knob inert. Accept
    it so the slider tracks drags without the panel being key."""

    def acceptsFirstMouse_(self, _event):  # noqa: N802
        return True


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
        self._recent_rgbs = []  # last two distinct picks (Duo Fade's pair)
        self._swatch_buttons = []
        self._build_status_item()
        self._build_panel()
        self._server = None
        if settings.control_port:
            try:
                self._server = ControlServer(self.controller, settings.control_port)
                self._server.start()
            except OSError as e:
                log.error("Control server failed to start: %s", e)
        self._timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            2.0, self, "refresh:", None, True
        )
        return self

    # ---- UI construction ------------------------------------------------------
    @objc.python_method
    def _build_status_item(self):
        self._item = NSStatusBar.systemStatusBar().statusItemWithLength_(NSVariableStatusItemLength)
        btn = self._item.button()
        btn.setTitle_(ICON_IDLE)
        btn.setTarget_(self)
        btn.setAction_("togglePanel:")

    @objc.python_method
    def _label(self, text, y, size=11, bold=False, color=None):
        lbl = NSTextField.labelWithString_(text)
        lbl.setFont_(NSFont.boldSystemFontOfSize_(size) if bold else NSFont.systemFontOfSize_(size))
        lbl.setTextColor_(color or NSColor.labelColor())
        lbl.setFrame_(NSMakeRect(MARGIN, y, WIDTH - 2 * MARGIN, size + 7))
        self._content.addSubview_(lbl)
        return lbl

    @objc.python_method
    def _swatch_button(self, rgb, frame, action, tag):
        b = NSButton.alloc().initWithFrame_(frame)
        b.setBordered_(False)
        b.setTitle_("")
        b.setImage_(NSImage.alloc().initWithContentsOfFile_(str(swatch_path(rgb))))
        b.setTarget_(self)
        b.setAction_(action)
        b.setTag_(tag)
        b.setWantsLayer_(True)
        b.layer().setCornerRadius_(7)
        self._content.addSubview_(b)
        return b

    @objc.python_method
    def _text_button(self, title, frame, action):
        b = NSButton.alloc().initWithFrame_(frame)
        b.setTitle_(title)
        b.setBezelStyle_(1)  # rounded
        b.setFont_(NSFont.systemFontOfSize_(11))
        b.setTarget_(self)
        b.setAction_(action)
        self._content.addSubview_(b)
        return b

    @objc.python_method
    def _build_panel(self):
        gap = (WIDTH - 2 * MARGIN - COLS * SWATCH) / (COLS - 1)
        rows = (len(COLORS) + COLS - 1) // COLS
        fx_titles = list(EFFECTS) + ["Stop Effect"]
        fx_rows = (len(fx_titles) + 1) // 2

        y = MARGIN
        header_y, y = y, y + 22
        status_y, y = y, y + 22
        colors_label_y, y = y, y + 18
        grid_y, y = y, y + rows * SWATCH + (rows - 1) * 8 + 10
        effects_label_y, y = y, y + 18
        fx_y, y = y, y + fx_rows * 26 + (fx_rows - 1) * 8 + 10
        bright_label_y, y = y, y + 16
        slider_y, y = y, y + 24
        footer_y, y = y, y + 26
        height = y + MARGIN

        style = NSWindowStyleMaskBorderless | NSWindowStyleMaskNonactivatingPanel
        self._panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, WIDTH, height), style, NSBackingStoreBuffered, False
        )
        self._panel.setLevel_(NSFloatingWindowLevel)
        self._panel.setOpaque_(False)
        self._panel.setBackgroundColor_(NSColor.clearColor())
        self._panel.setHidesOnDeactivate_(False)  # stays up while you use other apps
        self._panel.setBecomesKeyOnlyIfNeeded_(True)
        self._panel.setCollectionBehavior_(NSWindowCollectionBehaviorCanJoinAllSpaces)

        self._content = FlippedView.alloc().initWithFrame_(NSMakeRect(0, 0, WIDTH, height))
        self._content.setWantsLayer_(True)
        layer = self._content.layer()
        layer.setCornerRadius_(12)
        layer.setBackgroundColor_(NSColor.windowBackgroundColor().CGColor())
        layer.setBorderWidth_(1)
        layer.setBorderColor_(NSColor.separatorColor().CGColor())
        self._panel.setContentView_(self._content)

        self._label(APP_NAME, header_y, size=13, bold=True)
        self._status_label = self._label("Not connected — click a color", status_y,
                                         color=NSColor.secondaryLabelColor())
        self._status_label.setFrame_(NSMakeRect(MARGIN, status_y, WIDTH - 2 * MARGIN - 92, 18))
        self._connect_button = self._text_button(
            "Connect", NSMakeRect(WIDTH - MARGIN - 86, status_y - 2, 86, 22), "reconnectClicked:")
        self._label("COLORS", colors_label_y, size=10, color=NSColor.tertiaryLabelColor())
        for i, (_label, rgb) in enumerate(COLORS):
            r, c = divmod(i, COLS)
            frame = NSMakeRect(MARGIN + c * (SWATCH + gap), grid_y + r * (SWATCH + 8), SWATCH, SWATCH)
            b = self._swatch_button(rgb, frame, "colorClicked:", i)
            b.setToolTip_(_label)
            self._swatch_buttons.append(b)

        self._label("EFFECTS", effects_label_y, size=10, color=NSColor.tertiaryLabelColor())
        half = (WIDTH - 2 * MARGIN - 8) / 2
        for i, title in enumerate(fx_titles):
            r, c = divmod(i, 2)
            action = "stopClicked:" if title == "Stop Effect" else "effectClicked:"
            frame = NSMakeRect(MARGIN + c * (half + 8), fx_y + r * (26 + 8), half, 26)
            self._text_button(title, frame, action)

        self._label("BRIGHTNESS", bright_label_y, size=10, color=NSColor.tertiaryLabelColor())
        self._slider = FirstMouseSlider.alloc().initWithFrame_(
            NSMakeRect(MARGIN, slider_y, WIDTH - 2 * MARGIN, 20))
        self._slider.setMinValue_(0.05)
        self._slider.setMaxValue_(1.0)
        self._slider.setDoubleValue_(1.0)
        self._slider.setContinuous_(True)
        self._slider.setTarget_(self)
        self._slider.setAction_("brightnessChanged:")
        self._content.addSubview_(self._slider)

        quarter = (WIDTH - 2 * MARGIN - 3 * 8) / 4
        for i, (title, action) in enumerate([("Off", "offClicked:"), ("Log", "logClicked:"),
                                             ("Config", "configClicked:"), ("Quit", "quitClicked:")]):
            self._text_button(title, NSMakeRect(MARGIN + i * (quarter + 8), footer_y, quarter, 26), action)

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
        rgb = COLORS[sender.tag()][1]
        self._select(rgb)
        if rgb in self._recent_rgbs:
            self._recent_rgbs.remove(rgb)
        self._recent_rgbs.append(rgb)
        del self._recent_rgbs[:-2]  # keep the last two distinct picks
        self.controller.set_color(rgb)

    def effectClicked_(self, sender):  # noqa: N802
        label = str(sender.title())
        arity = EFFECTS[label].arity
        if arity == 0:
            colors = None
        elif arity == 1:
            colors = self._selected_rgb or DEFAULT_EFFECT_RGB
        else:  # two colors: the last two picked swatches, with friendly fallbacks
            pair = list(self._recent_rgbs)
            if len(pair) < 2:
                base = pair[0] if pair else DEFAULT_EFFECT_RGB
                other = DEFAULT_DUO_RGB if base != DEFAULT_DUO_RGB else DEFAULT_EFFECT_RGB
                pair = [base, other]
            colors = tuple(pair)
        self.controller.start_effect(label, colors)

    def stopClicked_(self, _sender):  # noqa: N802
        self.controller.stop_effect()

    def brightnessChanged_(self, sender):  # noqa: N802
        self.controller.set_brightness(float(sender.doubleValue()))

    def reconnectClicked_(self, _sender):  # noqa: N802
        self._status_label.setStringValue_("○ Scanning…")
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

    def refresh_(self, _timer):  # noqa: N802
        c = self.controller
        effect = f" · {c.current_effect}" if c.current_effect else ""
        if c.connected:
            self._status_label.setStringValue_(f"● Connected{effect}")
            self._item.button().setTitle_(ICON_CONNECTED)
            self._connect_button.setTitle_("Reconnect")
        elif c.last_error:
            self._status_label.setStringValue_(f"○ {c.last_error}")
            self._item.button().setTitle_(ICON_IDLE)
            self._connect_button.setTitle_("Connect")
        else:
            self._status_label.setStringValue_("○ Not connected — click a color")
            self._item.button().setTitle_(ICON_IDLE)
            self._connect_button.setTitle_("Connect")

    # ---- helpers ---------------------------------------------------------------
    @objc.python_method
    def _select(self, rgb):
        self._selected_rgb = rgb
        for i, b in enumerate(self._swatch_buttons):
            selected = rgb is not None and COLORS[i][1] == rgb
            b.layer().setBorderWidth_(2 if selected else 0)
            if selected:
                b.layer().setBorderColor_(NSColor.controlAccentColor().CGColor())


def run(settings: config.Settings) -> None:
    log.info("Starting %s panel app.", APP_NAME)
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(1)  # accessory: no Dock icon
    delegate = PanelApp.alloc().initWithSettings_(settings)
    assert delegate is not None
    app.run()

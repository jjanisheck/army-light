"""The rumps menu-bar app (daily-use mode).

Runs on the main/AppKit thread. Color clicks are handed to the WandController's
background loop; a periodic timer reflects connection status back into the menu
(no cross-thread UI calls). See controller.py for the threading model.
"""

from __future__ import annotations

import logging
import subprocess

import rumps

from . import APP_NAME, config
from .controller import WandController
from .palette import PALETTE

log = logging.getLogger(__name__)

ICON_CONNECTED = "💡"
ICON_IDLE = "🔅"


class ColorApp(rumps.App):
    def __init__(self, settings: config.Settings):
        super().__init__(ICON_IDLE, quit_button=None)
        self.settings = settings
        self.controller = WandController(settings)
        self.controller.start()

        color_items = [rumps.MenuItem(label, callback=self._make_color_cb(rgb))
                       for label, rgb in PALETTE]

        self._status_item = rumps.MenuItem("Not connected")  # no callback -> disabled

        self.menu = [
            *color_items,
            None,
            self._status_item,
            None,
            rumps.MenuItem("Test (Red)", callback=lambda _: self.controller.set_color((255, 0, 0))),
            rumps.MenuItem("Open log file…", callback=self._open_log),
            rumps.MenuItem("Open config file…", callback=self._open_config),
            None,
            rumps.MenuItem("Quit", callback=self._quit),
        ]

        # Reflect connection status into the menu/icon a couple times a second.
        self._timer = rumps.Timer(self._refresh_status, 2)
        self._timer.start()

    def _make_color_cb(self, rgb):
        return lambda _: self.controller.set_color(rgb)

    def _refresh_status(self, _timer):
        c = self.controller
        if c.connected:
            self._status_item.title = "● Connected"
            self.title = ICON_CONNECTED
        elif c.last_error:
            self._status_item.title = f"○ {c.last_error}"
            self.title = ICON_IDLE
        else:
            self._status_item.title = "○ Not connected — click a color"
            self.title = ICON_IDLE

    def _open_log(self, _):
        subprocess.run(["open", str(config.log_path())], check=False)

    def _open_config(self, _):
        subprocess.run(["open", str(config.config_path())], check=False)

    def _quit(self, _):
        log.info("Quitting.")
        self.controller.shutdown()
        rumps.quit_application()


def run(settings: config.Settings) -> None:
    log.info("Starting %s menu-bar app.", APP_NAME)
    ColorApp(settings).run()

"""Localhost HTTP remote control — Stream Deck / Apple Shortcuts / curl.

A tiny stdlib HTTP server bound to 127.0.0.1 only (never the network). Each GET
maps to one controller call, so a Stream Deck button can fire
`http://127.0.0.1:8722/color/red` and the running app does the rest:

    /color/<name|rrggbb|r,g,b>      set a solid color ("army-purple" works)
    /effect/<label>[?color=&color2=]start an effect ("glow-cycle", "duo-fade")
    /stop                            stop the running effect
    /off                             lights off
    /brightness/<0-100>              set brightness percent
    /reconnect                       drop + rescan + reconnect
    /status                          JSON state

Controller methods are thread-safe (they schedule onto its asyncio loop), so
the request threads call them directly.
"""

from __future__ import annotations

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

from . import effects
from .palette import parse_color

log = logging.getLogger(__name__)

DEFAULT_PORT = 8722


def _color(text: str):
    """URL-friendly color: palette name (dashes ok), bare hex, or r,g,b."""
    t = unquote(text).strip().lower().replace("-", " ").replace("_", " ")
    try:
        return parse_color(t)
    except ValueError:
        compact = t.replace(" ", "")
        if len(compact) == 6 and all(c in "0123456789abcdef" for c in compact):
            return parse_color("#" + compact)
        raise


def _effect_label(text: str) -> str:
    t = unquote(text).strip().lower().replace("-", " ").replace("_", " ")
    for label in effects.EFFECTS:
        if label.lower() == t:
            return label
    raise ValueError(f"Unknown effect {text!r}. Known: {', '.join(effects.EFFECTS)}")


class _Handler(BaseHTTPRequestHandler):
    controller = None  # injected via subclass in ControlServer

    def log_message(self, fmt, *args):  # quiet: route to our logger
        log.debug("control: " + fmt, *args)

    def _send(self, code: int, body: dict) -> None:
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):  # noqa: N802 (http.server API)
        url = urlparse(self.path)
        parts = [p for p in url.path.split("/") if p]
        query = parse_qs(url.query)
        c = self.controller
        try:
            if parts == ["status"]:
                self._send(200, {
                    "ok": True,
                    "connected": bool(c.connected),
                    "effect": c.current_effect,
                    "color": list(c.last_rgb) if c.last_rgb else None,
                    "brightness": c.brightness,
                })
            elif parts == ["off"]:
                c.set_color((0, 0, 0))
                self._send(200, {"ok": True})
            elif parts == ["stop"]:
                c.stop_effect()
                self._send(200, {"ok": True})
            elif parts == ["reconnect"]:
                c.reconnect()
                self._send(200, {"ok": True})
            elif len(parts) == 2 and parts[0] == "color":
                rgb = _color(parts[1])
                c.set_color(rgb)
                self._send(200, {"ok": True, "color": list(rgb)})
            elif len(parts) == 2 and parts[0] == "brightness":
                pct = float(parts[1])
                if not 0 <= pct <= 100:
                    raise ValueError("brightness must be 0-100")
                c.set_brightness(pct / 100.0)
                self._send(200, {"ok": True, "brightness": pct / 100.0})
            elif len(parts) == 2 and parts[0] == "effect":
                label = _effect_label(parts[1])
                arity = effects.EFFECTS[label].arity
                colors = None
                if arity >= 1 and "color" in query:
                    colors = _color(query["color"][0])
                    if arity == 2:
                        second = _color(query["color2"][0]) if "color2" in query else (255, 40, 150)
                        colors = (colors, second)
                c.start_effect(label, colors)
                self._send(200, {"ok": True, "effect": label})
            else:
                self._send(404, {"ok": False, "error": f"Unknown path {url.path!r}"})
        except (ValueError, KeyError) as e:
            self._send(400, {"ok": False, "error": str(e)})


class ControlServer:
    """Threaded localhost control server. port=0 picks an ephemeral port."""

    def __init__(self, controller, port: int = DEFAULT_PORT):
        handler = type("BoundHandler", (_Handler,), {"controller": controller})
        self._httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
        self._httpd.daemon_threads = True
        self._thread: threading.Thread | None = None

    @property
    def port(self) -> int:
        return self._httpd.server_address[1]

    def start(self) -> None:
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        log.info("Control server on http://127.0.0.1:%d", self.port)

    def stop(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()

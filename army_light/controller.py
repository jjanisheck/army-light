"""WandController — owns the BLE link and runs it on a private asyncio loop.

Threading model (see also the menu app): the menu UI lives on the main/AppKit
thread and must never block. All BLE work runs on a background asyncio loop owned
by this controller; the UI hands work across the boundary with `set_color()`,
which schedules a coroutine onto that loop.

Connection model (verified on a real V4 unit): a write to the ff13 "commit" char
makes the wand restart its BLE session — it applies the pending color, exits the
power-on pairing animation, and DROPS the link ~1-2s later. So each fresh
connection is "latched" exactly once (color + ff13, accept the drop, reconnect)
and afterwards plain ff01 color writes apply instantly over a persistent link
with no further commits. On write failure the client is dropped so the next call
reconnects (and re-latches) cleanly. An asyncio.Lock serializes writes.
"""

from __future__ import annotations

import asyncio
import logging
import threading

from bleak import BleakClient, BleakScanner

from . import effects, packets
from .config import Settings

log = logging.getLogger(__name__)


class WandController:
    # Seconds to let the wand restart its BLE session after a latch write.
    LATCH_DELAY = 1.0

    def __init__(self, settings: Settings):
        self.settings = settings
        self.client: BleakClient | None = None
        self.address: str = settings.wand_address

        # UI-readable status (read from the menu's refresh timer; no cross-thread
        # UI calls needed). Written only from the loop thread.
        self.connected: bool = False
        self.last_error: str | None = None
        self.last_rgb: tuple[int, int, int] | None = None
        self.current_effect: str | None = None
        self.brightness: float = 1.0  # software scaling — the wand has no register

        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._lock = asyncio.Lock()
        self._effect_task: asyncio.Task | None = None
        self._brightness_task: asyncio.Task | None = None

    # ---- lifecycle -----------------------------------------------------------
    def start(self) -> None:
        """Spin up the background event loop. Call once before set_color()."""
        if self._thread and self._thread.is_alive():
            return
        self._loop = asyncio.new_event_loop()
        self._lock = asyncio.Lock()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _run_loop(self) -> None:
        assert self._loop is not None
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def shutdown(self) -> None:
        if not self._loop:
            return
        asyncio.run_coroutine_threadsafe(self._disconnect(), self._loop)
        self._loop.call_soon_threadsafe(self._loop.stop)

    # ---- public API (call from any thread) -----------------------------------
    def set_color(self, rgb: tuple[int, int, int]) -> None:
        if not self._loop:
            log.error("Controller not started.")
            return
        asyncio.run_coroutine_threadsafe(self._set_color(rgb), self._loop)

    def start_effect(self, label: str, colors=None) -> None:
        """`colors`: None, one (r,g,b), or a sequence of them (per effect arity)."""
        if not self._loop:
            log.error("Controller not started.")
            return
        asyncio.run_coroutine_threadsafe(self._start_effect(label, colors), self._loop)

    def set_brightness(self, value: float) -> None:
        """Scale all output (solid colors and effect steps). Re-applies the
        current solid color; a running effect picks it up on its next step."""
        if not self._loop:
            return

        def _set() -> None:
            self.brightness = max(0.05, min(1.0, value))
            log.info("Brightness -> %.0f%% (effect=%s, last_rgb=%s)",
                     self.brightness * 100, self.current_effect, self.last_rgb)
            if self._effect_task or not self.last_rgb:
                return
            # Coalesce slider drags: one re-apply in flight at a time.
            if self._brightness_task and not self._brightness_task.done():
                return
            self._brightness_task = asyncio.ensure_future(self._reapply_brightness())

        self._loop.call_soon_threadsafe(_set)

    def stop_effect(self) -> None:
        if not self._loop:
            return
        self._loop.call_soon_threadsafe(self._cancel_effect)

    def reconnect(self) -> None:
        """Drop the current link (if any) and re-resolve from a fresh scan."""
        if not self._loop:
            log.error("Controller not started.")
            return
        asyncio.run_coroutine_threadsafe(self._reconnect(), self._loop)

    # ---- BLE internals (run on the loop thread) ------------------------------
    async def _resolve(self) -> str | None:
        if self.address:
            return self.address
        s = self.settings
        log.info("Scanning %.0fs for the wand…", s.scan_timeout)
        found = await BleakScanner.discover(timeout=s.scan_timeout, return_adv=True)
        # Prefer the Fanlight service UUID — robust regardless of advertised name.
        for dev, adv in found.values():
            uuids = [u.lower() for u in (adv.service_uuids or [])]
            if s.service_uuid.lower() in uuids:
                log.info("Found by service UUID: %s (%s)", dev.name or "?", dev.address)
                self.address = dev.address
                return dev.address
        # Fall back to a name substring match.
        for dev, adv in found.values():
            name = dev.name or adv.local_name or ""
            if s.wand_name_match and s.wand_name_match.lower() in name.lower():
                log.info("Found by name: %s (%s)", name, dev.address)
                self.address = dev.address
                return dev.address
        log.warning("Wand not found. Is it on, in Bluetooth mode, and unpaired from the phone?")
        return None

    async def _connect(self) -> bool:
        if self.client and self.client.is_connected:
            return True
        addr = await self._resolve()
        if not addr:
            self.last_error = "Wand not found"
            return False
        self.client = BleakClient(addr, timeout=self.settings.connect_timeout)
        try:
            await self.client.connect()
        except Exception as e:
            log.error("Connect failed: %s", e)
            self.last_error = f"Connect failed: {e}"
            self.client = None
            self.connected = False
            self.address = ""  # cached address may be stale — rescan next time
            return False
        self.connected = self.client.is_connected
        self.last_error = None
        log.info("Connected to %s.", addr)
        if self.connected and self.settings.wake_on_connect:
            await self._wake()
        return self.connected

    async def _wake(self) -> None:
        """Mimic the official app: subscribe to notifications and send a white
        wake packet so the link stays stable."""
        uuid = self.settings.color_char_uuid
        try:
            await self.client.start_notify(uuid, self._on_notify)
        except Exception as e:
            log.debug("start_notify skipped: %s", e)
        try:
            await self._write(packets.build(self.settings.packet_format, 255, 255, 255))
        except Exception as e:
            log.debug("wake write skipped: %s", e)

    def _on_notify(self, _sender, data: bytearray) -> None:
        log.debug("notify: %s", data.hex(" "))

    async def _write(self, packet: bytes) -> None:
        """Write with the configured response mode; retry with the other mode once."""
        uuid = self.settings.color_char_uuid
        primary = self.settings.write_with_response
        try:
            await self.client.write_gatt_char(uuid, packet, response=primary)
        except Exception as e:
            log.debug("write (response=%s) failed: %s; retrying response=%s", primary, e, not primary)
            await self.client.write_gatt_char(uuid, packet, response=not primary)

    def _packet_for(self, rgb: tuple[int, int, int], transition: int) -> bytes:
        scaled = tuple(min(255, round(c * self.brightness)) for c in rgb)
        if transition and self.settings.packet_format == "bts_v4":
            return packets.bts_v4(*scaled, transition=transition)
        return packets.build(self.settings.packet_format, *scaled)

    async def _ensure_link(self, rgb: tuple[int, int, int], transition: int = 0) -> bool:
        """Connected client, latched and ready for plain color writes.

        A fresh connection needs one latch — write the requested color plus the
        ff13 session-restart byte (so there's no color flash), let the wand drop
        the link, and reconnect. After that, ff01 writes apply instantly."""
        if self.client and self.client.is_connected:
            return True
        if not await self._connect():
            return False
        if not self.settings.commit_char_uuid:
            return True  # non-V4 formats: no latch dance
        try:
            await self._write(self._packet_for(rgb, transition))
            await self.client.write_gatt_char(
                self.settings.commit_char_uuid, packets.BTS_V4_COMMIT, response=False)
        except Exception as e:
            log.debug("latch write: %s", e)  # the wand may drop mid-latch; fine
        await self._disconnect()
        await asyncio.sleep(self.LATCH_DELAY)
        log.info("Latched; reconnecting for the persistent link.")
        return await self._connect()

    async def _apply(self, rgb: tuple[int, int, int], transition: int = 0) -> bool:
        """Write the color (+ optional fade) over a latched persistent link.
        Returns False on failure (client dropped so the next call reconnects)."""
        if not await self._ensure_link(rgb, transition):
            return False
        try:
            await self._write(self._packet_for(rgb, transition))
            self.last_rgb = rgb
            self.last_error = None
            return True
        except Exception as e:
            log.error("Write failed: %s", e)
            self.last_error = f"Write failed: {e}"
            self.connected = False
            self.client = None
            return False

    async def _set_color(self, rgb: tuple[int, int, int]) -> None:
        self._cancel_effect()
        async with self._lock:
            if await self._apply(rgb):
                log.info("Set color %s", rgb)

    async def _reapply_brightness(self) -> None:
        """Re-write the current color until the latest slider value sticks."""
        while True:
            target = self.brightness
            async with self._lock:
                if self._effect_task or not self.last_rgb:
                    return
                ok = await self._apply(self.last_rgb)
                log.info("Brightness %.0f%% applied to %s (ok=%s)",
                         target * 100, self.last_rgb, ok)
            if self.brightness == target:
                return

    async def _reconnect(self) -> None:
        async with self._lock:
            await self._disconnect()
            self.address = ""  # forget the cached address → fresh scan
            self.last_error = None
            log.info("Reconnect requested — rescanning.")
            await self._ensure_link(self.last_rgb or (255, 255, 255))

    # ---- effects (run on the loop thread) -------------------------------------
    def _cancel_effect(self) -> None:
        if self._effect_task:
            self._effect_task.cancel()
            self._effect_task = None
        self.current_effect = None

    @staticmethod
    def _effect_args(label: str, colors) -> tuple:
        """Normalize `colors` (None, one rgb, or a sequence of rgbs) to the
        argument tuple the effect's arity expects."""
        arity = effects.EFFECTS[label].arity
        if arity == 0 or colors is None:
            return ()
        if isinstance(colors[0], (tuple, list)):
            return tuple(tuple(c) for c in colors[:arity])
        return (tuple(colors),)

    async def _start_effect(self, label: str, colors=None) -> None:
        self._cancel_effect()
        steps = effects.EFFECTS[label].steps(*self._effect_args(label, colors))
        self._effect_task = asyncio.ensure_future(self._run_effect(steps))
        self.current_effect = label
        log.info("Effect started: %s %s", label, colors if colors else "")

    async def _run_effect(self, steps) -> None:
        """Drive one (rgb, transition, delay) step at a time. Failures drop the
        client and back off briefly; the next step reconnects."""
        for rgb, transition, delay in steps:
            async with self._lock:
                ok = await self._apply(rgb, transition)
            await asyncio.sleep(delay if ok else max(delay, 2.0))

    async def _disconnect(self) -> None:
        if self.client and self.client.is_connected:
            try:
                await self.client.disconnect()
            except Exception as e:
                log.debug("disconnect error: %s", e)
        self.client = None
        self.connected = False

"""WandController — owns the BLE link and runs it on a private asyncio loop.

Threading model (see also the menu app): the menu UI lives on the main/AppKit
thread and must never block. All BLE work runs on a background asyncio loop owned
by this controller; the UI hands work across the boundary with `set_color()`,
which schedules a coroutine onto that loop.

Connection model: the wand idle-disconnects, so we do NOT hold a persistent link.
Each write resolves+connects if needed, writes, and drops the client on failure so
the next call reconnects cleanly. An asyncio.Lock serializes writes.
"""

from __future__ import annotations

import asyncio
import logging
import threading

from bleak import BleakClient, BleakScanner

from . import packets
from .config import Settings

log = logging.getLogger(__name__)


class WandController:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client: BleakClient | None = None
        self.address: str = settings.wand_address

        # UI-readable status (read from the menu's refresh timer; no cross-thread
        # UI calls needed). Written only from the loop thread.
        self.connected: bool = False
        self.last_error: str | None = None
        self.last_rgb: tuple[int, int, int] | None = None

        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._lock = asyncio.Lock()

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

    async def _set_color(self, rgb: tuple[int, int, int]) -> None:
        async with self._lock:
            if not await self._connect():
                return
            try:
                await self._write(packets.build(self.settings.packet_format, *rgb))
                self.last_rgb = rgb
                self.last_error = None
                log.info("Set color %s", rgb)
            except Exception as e:
                log.error("Write failed: %s", e)
                self.last_error = f"Write failed: {e}"
                self.connected = False
                self.client = None

    async def _disconnect(self) -> None:
        if self.client and self.client.is_connected:
            try:
                await self.client.disconnect()
            except Exception as e:
                log.debug("disconnect error: %s", e)
        self.client = None
        self.connected = False

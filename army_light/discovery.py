"""Discovery workflow you run against the real wand to verify the protocol.

Order of operations:
    1. scan            find the wand and its address
    2. inspect <addr>  list every characteristic + its properties
    3. probe <addr>    fire candidate packets at a known color, find the winner
    4. monitor <addr>  watch notifications (useful if anything needs a handshake)

These are standalone (each opens its own client) and print human guidance — they
don't touch the menu app's controller.
"""

from __future__ import annotations

import asyncio

from bleak import BleakClient, BleakScanner

from . import packets
from .config import Settings
from .palette import parse_color


def _hl(addr: str, name: str, is_wand: bool) -> str:
    mark = "  <-- looks like the wand (Fanlight service)" if is_wand else ""
    return f"  {addr}   {name or '(no name)'}{mark}"


async def scan(settings: Settings) -> None:
    print(f"Scanning {settings.scan_timeout:.0f}s…\n")
    found = await BleakScanner.discover(timeout=settings.scan_timeout, return_adv=True)
    if not found:
        print("No BLE devices seen. Check macOS Bluetooth permission and that the wand is on.")
        return
    svc = settings.service_uuid.lower()
    rows = sorted(found.values(), key=lambda da: -(da[1].rssi or -999))
    for dev, adv in rows:
        uuids = [u.lower() for u in (adv.service_uuids or [])]
        is_wand = svc in uuids
        name = dev.name or adv.local_name or ""
        print(_hl(dev.address, name, is_wand))
        print(f"      rssi={adv.rssi} dBm   services={adv.service_uuids or []}")
        if adv.manufacturer_data:
            md = {k: v.hex() for k, v in adv.manufacturer_data.items()}
            print(f"      manufacturer_data={md}")
    print("\nNext: army-light inspect <address>")


async def inspect(settings: Settings, address: str) -> None:
    print(f"Connecting to {address}…\n")
    async with BleakClient(address, timeout=settings.connect_timeout) as client:
        print(f"Connected. MTU={getattr(client, 'mtu_size', '?')}\n")
        for service in client.services:
            print(f"[service] {service.uuid}  {service.description}")
            for char in service.characteristics:
                props = ",".join(char.properties)
                writable = ("write" in char.properties) or ("write-without-response" in char.properties)
                mark = "  <-- WRITABLE" if writable else ""
                print(f"    [char] {char.uuid}  ({props}){mark}")
        print("\nWritable characteristics are probe candidates. Next: army-light probe", address)


async def probe(settings: Settings, address: str, color: str = "red", char: str | None = None,
                fmts: list[str] | None = None) -> None:
    target = parse_color(color)
    fmts = fmts or list(packets.FORMATS.keys())
    print(f"Probe target color: {color} = {target}\n")
    async with BleakClient(address, timeout=settings.connect_timeout) as client:
        # Build the candidate characteristic list.
        if char:
            chars = [c for s in client.services for c in s.characteristics if c.uuid.lower() == char.lower()]
            if not chars:
                print(f"Characteristic {char} not found on device.")
                return
        else:
            chars = [c for s in client.services for c in s.characteristics
                     if {"write", "write-without-response"} & set(c.properties)]
        if not chars:
            print("No writable characteristics found.")
            return

        # Subscribe to notifications so we can see any responses.
        async def _notify(_s, data):
            print(f"      <- notify: {data.hex(' ')}")
        for c in chars:
            if "notify" in c.properties:
                try:
                    await client.start_notify(c.uuid, _notify)
                except Exception:
                    pass

        print(f"Trying {len(chars)} characteristic(s) x {len(fmts)} format(s).")
        print("Watch the wand. Type 'y' the moment it matches the target color.\n")
        for c in chars:
            for fmt in fmts:
                packet = packets.build(fmt, *target)
                resp = "write" in c.properties  # prefer with-response if supported
                try:
                    await client.write_gatt_char(c.uuid, packet, response=resp)
                except Exception as e:
                    print(f"  [{c.uuid} | {fmt}] write error: {e}")
                    continue
                print(f"  [{c.uuid} | {fmt}] sent {packet.hex(' ')}")
                prompt = "      did the wand change to the target color? [y/N/q] "
                answer = await asyncio.to_thread(input, prompt)
                a = answer.strip().lower()
                if a == "y":
                    print("\n*** MATCH ***  Lock these into config:")
                    print(f"    color_char_uuid    = {c.uuid}")
                    print(f"    packet_format      = {fmt}")
                    print(f"    write_with_response = {resp}")
                    print("\nRun: army-light set-config "
                          f"--char {c.uuid} --format {fmt} --response {str(resp).lower()}")
                    return
                if a == "q":
                    print("Stopped.")
                    return
        print("\nNo match found. Try `monitor` to watch for a handshake, or capture HCI logs.")


async def monitor(settings: Settings, address: str, send_queries: bool = True) -> None:
    print(f"Connecting to {address}… (Ctrl-C to stop)\n")
    async with BleakClient(address, timeout=settings.connect_timeout) as client:
        notify_chars = [c for s in client.services for c in s.characteristics if "notify" in c.properties]
        if not notify_chars:
            print("No notify characteristics to subscribe to.")
            return

        def _cb(uuid):
            def inner(_s, data):
                print(f"{uuid}  <- {data.hex(' ')}")
            return inner

        for c in notify_chars:
            await client.start_notify(c.uuid, _cb(c.uuid))
            print(f"Subscribed to {c.uuid}")

        if send_queries:
            # Poke the wand with Fanlight query packets to elicit responses.
            try:
                await client.write_gatt_char(settings.color_char_uuid, packets.QUERY_FIRMWARE, response=False)
                await client.write_gatt_char(settings.color_char_uuid, packets.QUERY_BATTERY, response=False)
            except Exception as e:
                print(f"(query write failed: {e})")

        print("\nWatching… press Ctrl-C to stop.")
        try:
            while True:
                await asyncio.sleep(1)
        except (KeyboardInterrupt, asyncio.CancelledError):
            print("\nStopped.")

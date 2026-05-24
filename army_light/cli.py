"""Command-line entry point: launch the menu app or run a discovery subcommand.

    army-light                 launch the menu-bar app (default)
    army-light scan            list nearby BLE devices
    army-light inspect <addr>  dump GATT services/characteristics
    army-light probe <addr>    find the write char + packet format interactively
    army-light monitor <addr>  watch notifications
    army-light set-config ...  persist verified protocol values

Legacy: `--scan` still works (it mapped to the old single-file behaviour).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from bleak.exc import BleakError

from . import APP_NAME, __version__, config, discovery, packets


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    try:
        handlers.append(logging.FileHandler(config.log_path()))
    except OSError:
        pass  # e.g. read-only FS; stderr still works
    logging.basicConfig(level=level, format="%(asctime)s  %(levelname)s  %(message)s", handlers=handlers)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="army-light", description=f"{APP_NAME} — control an ARMY Bomb over BLE.")
    p.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    p.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    p.add_argument("--scan", action="store_true", help=argparse.SUPPRESS)  # legacy alias

    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("scan", help="list nearby BLE devices")

    sp = sub.add_parser("inspect", help="dump GATT services/characteristics")
    sp.add_argument("address")

    sp = sub.add_parser("probe", help="find the write char + packet format")
    sp.add_argument("address")
    sp.add_argument("--color", default="red", help="target color name / r,g,b / #rrggbb")
    sp.add_argument("--char", default=None, help="restrict to one characteristic UUID")
    sp.add_argument("--format", dest="fmt", default=None, choices=list(packets.FORMATS),
                    help="restrict to one packet format")

    sp = sub.add_parser("monitor", help="watch notifications")
    sp.add_argument("address")

    sp = sub.add_parser("set-config", help="persist verified protocol values")
    sp.add_argument("--char")
    sp.add_argument("--format", dest="fmt", choices=list(packets.FORMATS))
    sp.add_argument("--response", choices=["true", "false"])
    sp.add_argument("--address", help="cache the wand's address")
    sp.add_argument("--service", help="advertised service UUID to match on")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    _setup_logging(args.verbose)
    settings = config.Settings.load()

    if args.scan and not args.cmd:
        args.cmd = "scan"

    def _run(coro) -> int:
        try:
            asyncio.run(coro)
            return 0
        except BleakError as e:
            print(f"\nBluetooth error: {e}", file=sys.stderr)
            print("Is Bluetooth on, and is your terminal granted Bluetooth access? "
                  "See SETUP.md §3.", file=sys.stderr)
            return 1
        except KeyboardInterrupt:
            return 130

    if args.cmd == "scan":
        return _run(discovery.scan(settings))
    elif args.cmd == "inspect":
        return _run(discovery.inspect(settings, args.address))
    elif args.cmd == "probe":
        fmts = [args.fmt] if args.fmt else None
        return _run(discovery.probe(settings, args.address, color=args.color, char=args.char, fmts=fmts))
    elif args.cmd == "monitor":
        return _run(discovery.monitor(settings, args.address))
    elif args.cmd == "set-config":
        if args.char:
            settings.color_char_uuid = args.char
        if args.fmt:
            settings.packet_format = args.fmt
        if args.response:
            settings.write_with_response = args.response == "true"
        if args.address:
            settings.wand_address = args.address
        if args.service:
            settings.service_uuid = args.service
        settings.save()
        print(f"Saved config to {config.config_path()}")
    else:
        # Default: launch the menu-bar app. Imported lazily so discovery
        # subcommands don't require rumps/AppKit.
        from . import app
        app.run(settings)
    return 0

"""Persistent settings + standard macOS file locations.

Settings live in ~/Library/Application Support/ArmyLight/config.json so they
survive across runs and across .app rebuilds. The discovery tooling writes the
verified protocol here; the menu-bar app reads it.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import APP_DIR_NAME

log = logging.getLogger(__name__)

# Set ARMYLIGHT_HOME to relocate config + logs (used by tests and power users).
_HOME_ENV = "ARMYLIGHT_HOME"


def support_dir() -> Path:
    """Where config.json lives. ~/Library/Application Support/ArmyLight by
    default; overridable via ARMYLIGHT_HOME. Created on demand."""
    override = os.environ.get(_HOME_ENV)
    p = Path(override) if override else Path.home() / "Library" / "Application Support" / APP_DIR_NAME
    p.mkdir(parents=True, exist_ok=True)
    return p


def logs_dir() -> Path:
    """Where the log file lives. ~/Library/Logs/ArmyLight by default;
    under ARMYLIGHT_HOME/logs when that override is set. Created on demand."""
    override = os.environ.get(_HOME_ENV)
    p = Path(override) / "logs" if override else Path.home() / "Library" / "Logs" / APP_DIR_NAME
    p.mkdir(parents=True, exist_ok=True)
    return p


def config_path() -> Path:
    return support_dir() / "config.json"


def log_path() -> Path:
    return logs_dir() / "army_light.log"


@dataclass
class Settings:
    """Everything the app needs to talk to the wand. Defaults are best guesses;
    the discovery tooling overwrites them with verified values."""

    # How to find the wand. The Fanlight service UUID is the robust matcher on
    # macOS (the BTS advertised name isn't publicly documented and may not
    # contain "ARMY"). Address is machine-specific on macOS (a CoreBluetooth
    # UUID, not a hardware MAC) so it isn't portable; resolve fresh each run.
    wand_address: str = ""
    wand_name_match: str = "ARMY"
    service_uuid: str = "00010203-0405-0607-0809-0a0b0c0d1911"

    # The write target + encoding. Confirmed against Fanlight-family sticks
    # (P1Harmony, LOONA) via decompiled official source + two working clients;
    # confirm on a BTS unit with `probe` if a color click does nothing.
    color_char_uuid: str = "00010203-0405-0607-0809-0a0b0c0d2b19"
    packet_format: str = "fanlight"
    write_with_response: bool = False  # app uses write-without-response

    # Mimic the official app: send a white "wake" packet right after connect and
    # subscribe to notifications on the write char to keep the link stable.
    wake_on_connect: bool = True

    # Behaviour.
    scan_timeout: float = 8.0
    connect_timeout: float = 12.0
    idle_color: list[int] = field(default_factory=lambda: [0, 0, 0])  # "off"

    @classmethod
    def load(cls) -> Settings:
        path = config_path()
        if not path.exists():
            s = cls()
            s.save()
            return s
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError) as e:
            log.warning("Could not read %s (%s); using defaults.", path, e)
            return cls()
        # Keep only known fields so stale/forward configs don't crash us.
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})

    def save(self) -> None:
        try:
            config_path().write_text(json.dumps(asdict(self), indent=2))
        except OSError as e:
            log.error("Could not write config: %s", e)

"""ARMY Light — control a BTS ARMY Bomb lightstick from the macOS menu bar over BLE."""

import os

__version__ = "0.3.0"

APP_NAME = "ARMY Light"
APP_DIR_NAME = "ArmyLight"
# Override with your own reverse-DNS id when building a personal .app
# (e.g. `export ARMYLIGHT_BUNDLE_ID=com.you.armylight`, or set it in a
# gitignored local.mk — see the Makefile).
BUNDLE_ID = os.environ.get("ARMYLIGHT_BUNDLE_ID", "com.example.armylight")

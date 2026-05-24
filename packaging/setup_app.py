"""Build the macOS .app bundle (py2app).

Use the Makefile: `make app` (runs this from the packaging/ dir so setuptools
doesn't pick up the repo's pyproject [project] table, which conflicts with the
imperative py2app setup call).

Manual equivalent:

    cd packaging
    PYTHONPATH=.. python setup_app.py py2app --dist-dir=../dist --bdist-base=../build

The bundle is a menu-bar agent (LSUIElement, no Dock icon) and declares its
Bluetooth usage so macOS attributes the permission prompt to ARMY Light.
"""

import os
import sys

from setuptools import setup

# Make the army_light package importable when run from this directory.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from army_light import APP_NAME, BUNDLE_ID, __version__  # noqa: E402

APP = ["app_main.py"]
BT_REASON = "ARMY Light uses Bluetooth to control your ARMY Bomb lightstick."

OPTIONS = {
    "argv_emulation": False,
    "packages": ["rumps", "bleak", "army_light"],
    "plist": {
        "CFBundleName": APP_NAME,
        "CFBundleDisplayName": APP_NAME,
        "CFBundleIdentifier": BUNDLE_ID,
        "CFBundleShortVersionString": __version__,
        "CFBundleVersion": __version__,
        "LSUIElement": True,  # menu-bar agent: no Dock icon, no window
        "NSBluetoothAlwaysUsageDescription": BT_REASON,
        "NSBluetoothPeripheralUsageDescription": BT_REASON,
    },
}

setup(
    app=APP,
    options={"py2app": OPTIONS},
)

"""Entry point for the bundled .app (py2app target).

The bundle always launches the menu-bar app; the discovery CLI is a developer
tool run via `army-light <cmd>` / `python -m army_light <cmd>`, not from the .app.
"""

from army_light.app import run
from army_light.config import Settings

if __name__ == "__main__":
    run(Settings.load())

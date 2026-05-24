"""Allow `python -m army_light`."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())

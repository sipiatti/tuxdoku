#!/usr/bin/python3
"""Launcher installed as /usr/bin/tuxdoku by the Debian package."""
import sys

sys.path.insert(0, "/usr/share/tuxdoku")

from tuxdoku.app import main  # noqa: E402

sys.exit(main())

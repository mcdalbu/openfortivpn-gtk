#!/usr/bin/python3
"""Launch the installed application from its private data directory."""

import sys

sys.path.insert(0, '@APPDIR@')

from openfortivpn_gtk.main import main


if __name__ == '__main__':
    sys.exit(main())

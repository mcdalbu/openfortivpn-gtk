#!/usr/bin/env python3
"""
OpenFortiVPN GTK - Entry point
"""

import sys
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gio

from openfortivpn_gtk.application import OpenFortiVPNApp


def main():
    """Application entry point."""
    app = OpenFortiVPNApp()
    return app.run(sys.argv)


if __name__ == '__main__':
    sys.exit(main())

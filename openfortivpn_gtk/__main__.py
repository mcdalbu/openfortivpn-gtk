"""Allow running as module: python -m openfortivpn_gtk"""
import sys

from openfortivpn_gtk.main import main

if __name__ == '__main__':
    sys.exit(main())

"""Persist application preferences separately from VPN credentials."""

import json
import os
import tempfile
from pathlib import Path


class AppSettings:
    def __init__(self, config_dir=None):
        self.config_dir = Path(config_dir) if config_dir else Path.home() / '.config' / 'openfortivpn-gtk'
        self.path = self.config_dir / 'settings.json'
        self.minimize_to_tray = False
        self.load_error = None
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
            value = data.get('minimize_to_tray', False)
            if not isinstance(value, bool):
                raise ValueError('Preferência de tray inválida')
            self.minimize_to_tray = value
        except FileNotFoundError:
            pass
        except (OSError, ValueError, AttributeError) as exc:
            self.load_error = str(exc)

    def set_minimize_to_tray(self, enabled):
        self.config_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, filename = tempfile.mkstemp(prefix='.settings-', dir=self.config_dir)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as file:
                json.dump({'minimize_to_tray': bool(enabled)}, file)
                file.flush()
                os.fsync(file.fileno())
            os.replace(filename, self.path)
        finally:
            if os.path.exists(filename):
                os.unlink(filename)
        self.minimize_to_tray = bool(enabled)
        self.load_error = None

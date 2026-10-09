import os
import stat
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from gi.repository import GLib

from openfortivpn_gtk.profile import ProfileManager, VPNProfile
from openfortivpn_gtk.vpn_manager import VPNManager, VPNState


def run_until(predicate, timeout=5):
    end = time.monotonic() + timeout
    context = GLib.MainContext.default()
    while time.monotonic() < end:
        while context.pending():
            context.iteration(False)
        if predicate():
            return True
        time.sleep(0.01)
    return False


class ProfileTests(unittest.TestCase):
    def test_dns_is_configured_by_openfortivpn_only(self):
        config = VPNProfile(host='vpn.example').to_config_file_content()
        self.assertIn('set-dns = 1\n', config)
        self.assertIn('pppd-use-peerdns = 0\n', config)
        self.assertNotIn('use-resolvconf', config)

    def test_config_rejects_newline_in_privileged_options(self):
        profile = VPNProfile(host='vpn.example', password='secret\nset-routes = 0')
        with self.assertRaises(ValueError):
            profile.to_config_file_content()

    def test_profiles_are_saved_atomically_and_privately(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch('openfortivpn_gtk.profile.Path.home', return_value=Path(directory)):
                manager = ProfileManager()
                manager.add(VPNProfile(host='vpn.example', password='secret'))
                self.assertEqual(stat.S_IMODE(manager.profiles_file.stat().st_mode), 0o600)
                self.assertEqual(stat.S_IMODE(manager.config_dir.stat().st_mode), 0o700)
                self.assertEqual(ProfileManager().profiles[0].host, 'vpn.example')

    def test_failed_save_does_not_change_in_memory_profiles(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch('openfortivpn_gtk.profile.Path.home', return_value=Path(directory)):
                manager = ProfileManager()
                with patch.object(manager, 'save', side_effect=OSError('sem espaço')):
                    with self.assertRaises(OSError):
                        manager.add(VPNProfile(host='vpn.example'))
                self.assertEqual(manager.profiles, [])

    def test_invalid_profiles_file_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            config_dir = Path(directory) / '.config' / 'openfortivpn-gtk'
            config_dir.mkdir(parents=True)
            profiles_file = config_dir / 'profiles.json'
            profiles_file.write_text('{invalid json')
            with patch('openfortivpn_gtk.profile.Path.home', return_value=Path(directory)):
                manager = ProfileManager()
                with self.assertRaises(OSError):
                    manager.add(VPNProfile(host='vpn.example'))
            self.assertEqual(profiles_file.read_text(), '{invalid json')


class ConnectionTests(unittest.TestCase):
    def test_launch_failure_removes_temporary_config(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = VPNManager()
            real_mkstemp = tempfile.mkstemp

            def create_config(**kwargs):
                return real_mkstemp(dir=directory, **kwargs)

            with patch.object(manager, '_find_system_executable', side_effect=lambda name: f'/usr/bin/{name}'), \
                    patch('openfortivpn_gtk.vpn_manager.tempfile.mkstemp', side_effect=create_config), \
                    patch('openfortivpn_gtk.vpn_manager.subprocess.Popen', side_effect=OSError('falha')):
                self.assertFalse(manager.connect_vpn(VPNProfile(host='vpn.example')))
            self.assertEqual(manager.state, VPNState.DISCONNECTED)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_prompt_connect_disconnect_and_secret_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runner = root / 'pkexec'
            runner.write_text('#!/bin/sh\nexec "$@"\n')
            runner.chmod(0o700)
            vpn = root / 'openfortivpn'
            vpn.write_text(
                '#!/usr/bin/env python3\n'
                'import sys, time\n'
                'sys.stdout.write("Enter OTP:")\n'
                'sys.stdout.flush()\n'
                'sys.stdin.readline()\n'
                'print("Tunnel is up and running", flush=True)\n'
                'time.sleep(30)\n'
            )
            vpn.chmod(0o700)
            paths = {'pkexec': str(runner), 'openfortivpn': str(vpn),
                     'setsid': '/usr/bin/setsid'}
            manager = VPNManager()
            prompts, logs = [], []
            manager.connect('otp-required', lambda *_: prompts.append(True))
            manager.connect('log-message', lambda _, message: logs.append(message))
            with patch.object(manager, '_find_system_executable', side_effect=paths.get):
                self.assertTrue(manager.connect_vpn(VPNProfile(host='vpn.example')))
            config_file = Path(manager._read_thread._args[2])
            self.assertTrue(config_file.exists())
            self.assertEqual(stat.S_IMODE(config_file.stat().st_mode), 0o600)
            self.assertTrue(run_until(lambda: prompts))
            manager.send_input('987654')
            self.assertTrue(run_until(lambda: manager.state == VPNState.CONNECTED))
            started = time.monotonic()
            manager.disconnect()
            self.assertLess(time.monotonic() - started, 0.5)
            self.assertTrue(run_until(lambda: manager.state == VPNState.DISCONNECTED))
            self.assertFalse(config_file.exists())
            self.assertNotIn('987654', '\n'.join(logs))


if __name__ == '__main__':
    unittest.main()

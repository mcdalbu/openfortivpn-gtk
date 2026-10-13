import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from gi.repository import Gio, GLib

from openfortivpn_gtk.application import OpenFortiVPNApp
from openfortivpn_gtk.settings import AppSettings
from openfortivpn_gtk.tray import TrayIndicator, WATCHER, WATCHER_PATH, ITEM_INTERFACE, ITEM_PATH, MENU_INTERFACE, MENU_PATH
from test_core import run_until


class SettingsTests(unittest.TestCase):
    def test_preference_survives_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = AppSettings(directory)
            self.assertFalse(settings.minimize_to_tray)
            settings.set_minimize_to_tray(True)
            self.assertTrue(AppSettings(directory).minimize_to_tray)
            self.assertEqual(json.loads(settings.path.read_text()), {'minimize_to_tray': True})

    def test_failed_save_keeps_previous_preference(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = AppSettings(directory)
            with patch('openfortivpn_gtk.settings.os.replace', side_effect=OSError('sem espaço')):
                with self.assertRaises(OSError):
                    settings.set_minimize_to_tray(True)
            self.assertFalse(settings.minimize_to_tray)
            self.assertEqual(list(Path(directory).iterdir()), [])


class CloseBehaviorTests(unittest.TestCase):
    def app(self, enabled=True, available=True):
        return SimpleNamespace(
            _quitting=False, settings=SimpleNamespace(minimize_to_tray=enabled),
            tray=SimpleNamespace(available=available), _background_hold=False,
            hold=Mock(), activate=Mock(), window=Mock())

    def test_close_hides_window_without_disconnecting(self):
        app = self.app()
        self.assertTrue(OpenFortiVPNApp._on_close_request(app, app.window))
        app.window.set_visible.assert_called_once_with(False)
        app.window.vpn_manager.disconnect.assert_not_called()
        app.hold.assert_called_once()

    def test_missing_tray_keeps_window_accessible(self):
        app = self.app(available=False)
        self.assertTrue(OpenFortiVPNApp._on_close_request(app, app.window))
        app.window.set_visible.assert_not_called()
        app.window.show_toast.assert_called_once()

    def test_disabled_preference_or_quit_allows_normal_close(self):
        for enabled, quitting in ((False, False), (True, True)):
            app = self.app(enabled=enabled)
            app._quitting = quitting
            self.assertFalse(OpenFortiVPNApp._on_close_request(app, app.window))
            app.window.set_visible.assert_not_called()

    def test_lost_tray_restores_hidden_window(self):
        app = self.app(available=False)
        app._background_hold = True
        OpenFortiVPNApp._on_tray_available(app, False)
        app.activate.assert_called_once()


WATCHER_XML = '''<node><interface name="org.kde.StatusNotifierWatcher">
<method name="RegisterStatusNotifierItem"><arg type="s" direction="in"/></method>
<property name="IsStatusNotifierHostRegistered" type="b" access="read"/>
<signal name="StatusNotifierHostRegistered"/>
<signal name="StatusNotifierHostUnregistered"/>
</interface></node>'''


class TrayProtocolTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.daemon = subprocess.Popen(
            ['/usr/bin/dbus-daemon', '--session', '--nofork', '--print-address=1',
             f'--address=unix:path={self.directory.name}/bus'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(self.stop_daemon)
        address = self.daemon.stdout.readline().strip()
        if not address:
            raise RuntimeError(self.daemon.stderr.read())
        flags = Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION
        self.server = Gio.DBusConnection.new_for_address_sync(address, flags, None, None)
        self.client = Gio.DBusConnection.new_for_address_sync(address, flags, None, None)
        self.has_host = True
        self.registrations = []
        self.object_id = self.server.register_object(
            WATCHER_PATH, Gio.DBusNodeInfo.new_for_xml(WATCHER_XML).interfaces[0],
            self.register_item, lambda *args: GLib.Variant('b', self.has_host), None)
        self.owner = Gio.bus_own_name_on_connection(self.server, WATCHER, Gio.BusNameOwnerFlags.NONE, None, None)
        self.show, self.disconnect, self.quit = Mock(), Mock(), Mock()
        self.availability = []
        with patch.object(TrayIndicator, '_load_pixmaps', return_value=[]):
            self.tray = TrayIndicator(self.show, self.disconnect, self.quit, self.availability.append)
        self.tray.start(self.server)
        self.assertTrue(run_until(lambda: self.tray.available))

    def register_item(self, connection, sender, path, interface, method, parameters, invocation):
        self.registrations.append(parameters.unpack()[0])
        invocation.return_value(None)

    def tearDown(self):
        self.tray.stop()
        Gio.bus_unown_name(self.owner)
        self.server.unregister_object(self.object_id)
        self.client.close_sync(None)
        self.server.close_sync(None)

    def stop_daemon(self):
        if self.daemon.poll() is None:
            self.daemon.terminate()
            self.daemon.wait(timeout=3)
        self.daemon.stdout.close()
        self.daemon.stderr.close()

    def call(self, path, interface, method, parameters):
        replies, errors = [], []

        def done(connection, result):
            try:
                replies.append(connection.call_finish(result))
            except GLib.Error as exc:
                errors.append(exc)

        self.client.call(self.server.get_unique_name(), path, interface, method,
                         parameters, None, Gio.DBusCallFlags.NONE, 2000, None, done)
        self.assertTrue(run_until(lambda: replies or errors))
        if errors:
            raise errors[0]
        return replies[0]

    def click(self, item_id):
        self.call(MENU_PATH, MENU_INTERFACE, 'Event',
                  GLib.Variant('(isvu)', (item_id, 'clicked', GLib.Variant('s', ''), 0)))

    def test_registration_menu_and_actions(self):
        self.assertEqual(self.registrations, [ITEM_PATH])
        reply = self.call(ITEM_PATH, 'org.freedesktop.DBus.Properties', 'GetAll',
                          GLib.Variant('(s)', (ITEM_INTERFACE,))).unpack()[0]
        self.assertEqual(reply['IconName'], 'openfortivpn-gtk')
        self.assertEqual(reply['Menu'], MENU_PATH)
        layout = self.call(MENU_PATH, MENU_INTERFACE, 'GetLayout',
                           GLib.Variant('(iias)', (0, -1, []))).unpack()
        children = {item[0]: item[1] for item in layout[1][2]}
        self.assertFalse(children[3]['enabled'])
        self.click(3)
        self.disconnect.assert_not_called()
        self.tray.update('connected', SimpleNamespace(name='VPN da empresa'))
        layout = self.call(MENU_PATH, MENU_INTERFACE, 'GetLayout',
                           GLib.Variant('(iias)', (0, -1, []))).unpack()
        children = {item[0]: item[1] for item in layout[1][2]}
        self.assertTrue(children[3]['enabled'])
        self.assertIn('VPN da empresa', children[2]['label'])
        for item_id in (1, 3, 5):
            self.click(item_id)
        self.assertTrue(run_until(lambda: self.quit.called))
        self.show.assert_called_once()
        self.disconnect.assert_called_once()
        self.quit.assert_called_once()

    def test_host_loss_and_recovery(self):
        self.has_host = False
        self.server.emit_signal(None, WATCHER_PATH, WATCHER, 'StatusNotifierHostUnregistered', None)
        self.assertTrue(run_until(lambda: not self.tray.available))
        self.has_host = True
        self.server.emit_signal(None, WATCHER_PATH, WATCHER, 'StatusNotifierHostRegistered', None)
        self.assertTrue(run_until(lambda: self.tray.available))
        self.assertEqual(self.availability, [False, True, False, True])

    def test_stop_unregisters_item_and_menu(self):
        self.tray.stop()
        self.assertFalse(self.tray.available)
        with self.assertRaises(GLib.Error):
            self.call(MENU_PATH, MENU_INTERFACE, 'GetLayout', GLib.Variant('(iias)', (0, -1, [])))

    def test_watcher_restart_registers_item_again(self):
        Gio.bus_unown_name(self.owner)
        self.assertTrue(run_until(lambda: not self.tray.available))
        self.owner = Gio.bus_own_name_on_connection(self.server, WATCHER, Gio.BusNameOwnerFlags.NONE, None, None)
        self.assertTrue(run_until(lambda: self.tray.available))
        self.assertEqual(self.registrations, [ITEM_PATH, ITEM_PATH])


if __name__ == '__main__':
    unittest.main()

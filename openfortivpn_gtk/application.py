"""
Application - Main GTK Application class
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gio, GLib

from openfortivpn_gtk.window import MainWindow
from openfortivpn_gtk.settings import AppSettings
from openfortivpn_gtk.tray import TrayIndicator


class OpenFortiVPNApp(Adw.Application):
    """Main application class."""
    
    def __init__(self):
        super().__init__(
            application_id='com.github.openfortivpn.gtk',
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS
        )
        
        self.window = None
        self.settings = AppSettings()
        self.tray = None
        self._background_hold = False
        self._quitting = False
        
        # Set up actions
        self._setup_actions()

    def _setup_actions(self):
        """Set up application actions."""
        # Quit action
        quit_action = Gio.SimpleAction.new('quit', None)
        quit_action.connect('activate', self._on_quit)
        self.add_action(quit_action)
        self.set_accels_for_action('app.quit', ['<Control>q'])
        
        # New profile action
        new_action = Gio.SimpleAction.new('new-profile', None)
        new_action.connect('activate', self._on_new_profile)
        self.add_action(new_action)
        self.set_accels_for_action('app.new-profile', ['<Control>n'])
    
    def do_activate(self):
        """Handle application activation."""
        if not self.window:
            self.window = MainWindow(application=self)
            self.window.connect('close-request', self._on_close_request)
            self.tray = TrayIndicator(
                on_show=self.activate, on_disconnect=self.window.vpn_manager.disconnect,
                on_quit=lambda: self._on_quit(None, None),
                on_available=self._on_tray_available)
            self.window.vpn_manager.connect('state-changed', self._on_tray_state)
            self.tray.start()
        
        if self._background_hold:
            self.release()
            self._background_hold = False
        if self.tray.activation_token:
            self.window.set_startup_id(self.tray.activation_token)
            self.tray.activation_token = None
        self.window.present()

    def _on_close_request(self, window):
        if self._quitting or not self.settings.minimize_to_tray:
            return False
        if not self.tray or not self.tray.available:
            window.show_toast("Tray indisponível. Use Sair no menu para encerrar o aplicativo.")
            return True
        if not self._background_hold:
            self.hold()
            self._background_hold = True
        window.set_visible(False)
        return True

    def _on_tray_available(self, available):
        if self._quitting:
            return
        self.window.update_tray_hint(available)
        if not available and self._background_hold:
            self.activate()
            self.window.show_toast("A área de notificação ficou indisponível; a janela foi reaberta.")

    def _on_tray_state(self, manager, state):
        self.tray.update(state, manager.current_profile)
    
    def _on_quit(self, action, param):
        """Handle quit action."""
        self._quitting = True
        self.quit()

    def do_shutdown(self):
        self._quitting = True
        if self.tray:
            self.tray.stop()
        if self.window:
            self.window.vpn_manager.disconnect(wait=True)
        if self._background_hold:
            self.release()
            self._background_hold = False
        Adw.Application.do_shutdown(self)
    
    def _on_new_profile(self, action, param):
        """Handle new profile action."""
        if self.window:
            self.window._on_add_profile(None)

"""
Application - Main GTK Application class
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gio, GLib

from openfortivpn_gtk.window import MainWindow


class OpenFortiVPNApp(Adw.Application):
    """Main application class."""
    
    def __init__(self):
        super().__init__(
            application_id='com.github.openfortivpn.gtk',
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS
        )
        
        self.window = None
        
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
        
        self.window.present()
    
    def _on_quit(self, action, param):
        """Handle quit action."""
        self.quit()

    def do_shutdown(self):
        if self.window:
            self.window.vpn_manager.disconnect(wait=True)
        Adw.Application.do_shutdown(self)
    
    def _on_new_profile(self, action, param):
        """Handle new profile action."""
        if self.window:
            self.window._on_add_profile(None)

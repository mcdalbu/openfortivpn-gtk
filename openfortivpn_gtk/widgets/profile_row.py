"""
Profile Row - Widget for displaying a VPN profile in the list
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GObject

from openfortivpn_gtk.profile import VPNProfile
from openfortivpn_gtk.vpn_manager import VPNState


class ProfileRow(Adw.ActionRow):
    """A row widget representing a VPN profile."""
    
    __gsignals__ = {
        'connect-clicked': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'edit-clicked': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'delete-clicked': (GObject.SignalFlags.RUN_FIRST, None, ()),
    }
    
    def __init__(self, profile: VPNProfile, **kwargs):
        super().__init__(**kwargs)
        
        self.profile = profile
        self._state = VPNState.DISCONNECTED
        
        self._build_ui()
        self.update_from_profile()
    
    def _build_ui(self):
        """Build the row UI."""
        # Status icon
        self.status_icon = Gtk.Image.new_from_icon_name("network-vpn-symbolic")
        self.status_icon.add_css_class('dim-label')
        self.add_prefix(self.status_icon)
        
        # Action buttons box
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        button_box.set_valign(Gtk.Align.CENTER)
        
        # Edit button
        edit_btn = Gtk.Button.new_from_icon_name("document-edit-symbolic")
        edit_btn.set_valign(Gtk.Align.CENTER)
        edit_btn.add_css_class('flat')
        edit_btn.set_tooltip_text("Editar")
        edit_btn.connect('clicked', lambda _: self.emit('edit-clicked'))
        button_box.append(edit_btn)
        
        # Delete button
        delete_btn = Gtk.Button.new_from_icon_name("user-trash-symbolic")
        delete_btn.set_valign(Gtk.Align.CENTER)
        delete_btn.add_css_class('flat')
        delete_btn.add_css_class('error')
        delete_btn.set_tooltip_text("Excluir")
        delete_btn.connect('clicked', lambda _: self.emit('delete-clicked'))
        button_box.append(delete_btn)
        
        # Connect button
        self.connect_btn = Gtk.Button(label="Conectar")
        self.connect_btn.set_valign(Gtk.Align.CENTER)
        self.connect_btn.add_css_class('suggested-action')
        self.connect_btn.connect('clicked', lambda _: self.emit('connect-clicked'))
        button_box.append(self.connect_btn)
        
        self.add_suffix(button_box)
        
        self.set_activatable(False)
    
    def update_from_profile(self):
        """Update row from profile data."""
        self.set_title(self.profile.name)
        
        subtitle = self.profile.host
        if self.profile.port and self.profile.port != 443:
            subtitle += f":{self.profile.port}"
        if self.profile.username:
            subtitle = f"{self.profile.username}@{subtitle}"
        
        self.set_subtitle(subtitle)
    
    def set_connection_state(self, state: VPNState, is_this_profile: bool = False):
        """Update the row based on connection state."""
        self._state = state
        
        if is_this_profile:
            if state == VPNState.CONNECTED:
                self.status_icon.set_from_icon_name("network-vpn-symbolic")
                self.status_icon.remove_css_class('dim-label')
                self.status_icon.remove_css_class('error')
                self.status_icon.add_css_class('success')
                self.connect_btn.set_label("Desconectar")
                self.connect_btn.remove_css_class('suggested-action')
                self.connect_btn.add_css_class('destructive-action')
            elif state == VPNState.CONNECTING:
                self.status_icon.set_from_icon_name("network-vpn-acquiring-symbolic")
                self.status_icon.remove_css_class('dim-label')
                self.status_icon.remove_css_class('success')
                self.status_icon.remove_css_class('error')
                self.connect_btn.set_label("Cancelar")
                self.connect_btn.set_sensitive(True)
            elif state == VPNState.DISCONNECTING:
                self.connect_btn.set_label("Desconectando...")
                self.connect_btn.set_sensitive(False)
            elif state == VPNState.ERROR:
                self.status_icon.set_from_icon_name("dialog-error-symbolic")
                self.status_icon.remove_css_class('success')
                self.status_icon.add_css_class('error')
                self.connect_btn.set_label("Conectar")
                self.connect_btn.set_sensitive(True)
                self.connect_btn.remove_css_class('destructive-action')
                self.connect_btn.add_css_class('suggested-action')
            else:  # DISCONNECTED
                self._reset_to_disconnected()
        else:
            # Not this profile
            if state in (VPNState.CONNECTING, VPNState.CONNECTED, VPNState.DISCONNECTING):
                # Another profile is connected, disable this one
                self.connect_btn.set_sensitive(False)
                self.connect_btn.set_label("Conectar")
            else:
                self._reset_to_disconnected()
    
    def _reset_to_disconnected(self):
        """Reset row to disconnected state."""
        self.status_icon.set_from_icon_name("network-vpn-symbolic")
        self.status_icon.remove_css_class('success')
        self.status_icon.remove_css_class('error')
        self.status_icon.add_css_class('dim-label')
        self.connect_btn.set_label("Conectar")
        self.connect_btn.set_sensitive(True)
        self.connect_btn.remove_css_class('destructive-action')
        self.connect_btn.add_css_class('suggested-action')

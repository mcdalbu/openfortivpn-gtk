"""
Profile Dialog - Dialog for creating and editing VPN profiles
"""

from dataclasses import replace

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GObject

from openfortivpn_gtk.profile import VPNProfile


class ProfileDialog(Adw.Dialog):
    """Dialog for creating or editing a VPN profile."""
    
    __gsignals__ = {
        'profile-saved': (GObject.SignalFlags.RUN_FIRST, None, (object,)),
    }
    
    def __init__(self, profile: VPNProfile = None, **kwargs):
        super().__init__(**kwargs)
        
        self.profile = replace(profile) if profile is not None else VPNProfile()
        self.is_new = profile is None
        
        self.set_title("Novo Perfil" if self.is_new else "Editar Perfil")
        self.set_content_width(500)
        self.set_content_height(600)
        
        self._build_ui()
        self._populate_fields()
    
    def _build_ui(self):
        """Build the dialog UI."""
        # Main box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        
        # Header bar
        header = Adw.HeaderBar()
        header.set_show_end_title_buttons(False)
        header.set_show_start_title_buttons(False)
        
        # Cancel button
        cancel_btn = Gtk.Button(label="Cancelar")
        cancel_btn.connect('clicked', lambda _: self.close())
        header.pack_start(cancel_btn)
        
        # Save button
        save_btn = Gtk.Button(label="Salvar")
        save_btn.add_css_class('suggested-action')
        save_btn.connect('clicked', self._on_save)
        header.pack_end(save_btn)
        
        main_box.append(header)
        
        # Scrollable content
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)
        
        # Content box with margins
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        content.set_margin_start(24)
        content.set_margin_end(24)
        content.set_margin_top(24)
        content.set_margin_bottom(24)
        
        # Basic Settings Group
        basic_group = Adw.PreferencesGroup(title="Configurações Básicas")
        
        # Profile name
        self.name_row = Adw.EntryRow(title="Nome do Perfil")
        basic_group.add(self.name_row)
        
        # Host
        self.host_row = Adw.EntryRow(title="Servidor VPN")
        self.host_row.set_input_purpose(Gtk.InputPurpose.URL)
        basic_group.add(self.host_row)
        
        # Port
        self.port_row = Adw.SpinRow.new_with_range(1, 65535, 1)
        self.port_row.set_title("Porta")
        self.port_row.set_value(443)
        basic_group.add(self.port_row)
        
        content.append(basic_group)
        
        # Authentication Group
        auth_group = Adw.PreferencesGroup(title="Autenticação")
        
        # Username
        self.username_row = Adw.EntryRow(title="Usuário")
        auth_group.add(self.username_row)
        
        # Password
        self.password_row = Adw.PasswordEntryRow(title="Senha")
        auth_group.add(self.password_row)
        
        # Realm
        self.realm_row = Adw.EntryRow(title="Realm (opcional)")
        auth_group.add(self.realm_row)
        
        # OTP
        self.otp_row = Adw.EntryRow(title="OTP (opcional)")
        auth_group.add(self.otp_row)
        
        content.append(auth_group)
        
        # Security Group
        security_group = Adw.PreferencesGroup(title="Segurança")
        
        # Trusted cert
        self.cert_row = Adw.EntryRow(title="Certificado Confiável (SHA256)")
        self.cert_row.set_input_purpose(Gtk.InputPurpose.FREE_FORM)
        security_group.add(self.cert_row)
        
        # User certificate
        self.user_cert_row = Adw.EntryRow(title="Certificado do Usuário (caminho)")
        security_group.add(self.user_cert_row)
        
        # User key
        self.user_key_row = Adw.EntryRow(title="Chave do Usuário (caminho)")
        security_group.add(self.user_key_row)
        
        content.append(security_group)
        
        # Network Group
        network_group = Adw.PreferencesGroup(title="Rede")
        
        # Set routes
        self.routes_row = Adw.SwitchRow(title="Configurar Rotas")
        self.routes_row.set_subtitle("Adicionar rotas VPN automaticamente")
        network_group.add(self.routes_row)
        
        # Set DNS
        self.dns_row = Adw.SwitchRow(title="Configurar DNS")
        self.dns_row.set_subtitle("Usar servidores DNS da VPN")
        network_group.add(self.dns_row)
        
        # Half internet routes
        self.half_routes_row = Adw.SwitchRow(title="Rotas Half-Internet")
        self.half_routes_row.set_subtitle("Usar duas rotas /1 em vez de rota padrão")
        network_group.add(self.half_routes_row)
        
        content.append(network_group)
        
        scrolled.set_child(content)
        main_box.append(scrolled)
        
        self.set_child(main_box)

        self.error_label = Gtk.Label()
        self.error_label.add_css_class('error')
        self.error_label.set_wrap(True)
        self.error_label.set_visible(False)
        content.prepend(self.error_label)
    
    def _populate_fields(self):
        """Populate fields with profile data."""
        self.name_row.set_text(self.profile.name)
        self.host_row.set_text(self.profile.host)
        self.port_row.set_value(self.profile.port)
        self.username_row.set_text(self.profile.username)
        self.password_row.set_text(self.profile.password)
        self.realm_row.set_text(self.profile.realm)
        self.otp_row.set_text(self.profile.otp)
        self.cert_row.set_text(self.profile.trusted_cert)
        self.user_cert_row.set_text(self.profile.user_cert)
        self.user_key_row.set_text(self.profile.user_key)
        self.routes_row.set_active(self.profile.set_routes)
        self.dns_row.set_active(self.profile.set_dns)
        self.half_routes_row.set_active(self.profile.half_internet_routes)
    
    def _on_save(self, button):
        """Handle save button click."""
        # Update profile from fields
        self.profile.name = self.name_row.get_text().strip() or "Nova Conexão"
        self.profile.host = self.host_row.get_text().strip()
        self.profile.port = int(self.port_row.get_value())
        self.profile.username = self.username_row.get_text()
        self.profile.password = self.password_row.get_text()
        self.profile.realm = self.realm_row.get_text()
        self.profile.otp = self.otp_row.get_text()
        self.profile.trusted_cert = self.cert_row.get_text()
        self.profile.user_cert = self.user_cert_row.get_text()
        self.profile.user_key = self.user_key_row.get_text()
        self.profile.set_routes = self.routes_row.get_active()
        self.profile.set_dns = self.dns_row.get_active()
        self.profile.half_internet_routes = self.half_routes_row.get_active()

        try:
            self.profile.to_config_file_content()
        except ValueError as exc:
            self.error_label.set_label(str(exc))
            self.error_label.set_visible(True)
            return
        
        # Emit signal
        self.save_ok = True
        self.emit('profile-saved', self.profile)
        if self.save_ok:
            self.close()

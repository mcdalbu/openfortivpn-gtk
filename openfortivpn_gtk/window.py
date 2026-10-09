"""
Main Window - Primary application window
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Pango

from openfortivpn_gtk.profile import VPNProfile, ProfileManager
from openfortivpn_gtk.vpn_manager import VPNManager, VPNState
from openfortivpn_gtk.widgets.profile_row import ProfileRow
from openfortivpn_gtk.widgets.profile_dialog import ProfileDialog


class MainWindow(Adw.ApplicationWindow):
    """Main application window."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        self.set_title("OpenFortiVPN")
        self.set_default_size(700, 600)
        
        # Initialize managers
        self.profile_manager = ProfileManager()
        self.vpn_manager = VPNManager()
        
        # Connect VPN manager signals
        self.vpn_manager.connect('state-changed', self._on_state_changed)
        self.vpn_manager.connect('log-message', self._on_log_message)
        self.vpn_manager.connect('error', self._on_vpn_error)
        self.vpn_manager.connect('otp-required', self._on_otp_required)
        self.vpn_manager.connect('password-required', self._on_password_required)
        
        # Profile rows mapping
        self._profile_rows = {}
        
        self._build_ui()
        self._load_profiles()
        if self.profile_manager.load_error:
            self._on_vpn_error(self.vpn_manager, "Não foi possível carregar os perfis; confira profiles.json")
    
    def _build_ui(self):
        """Build the window UI."""
        # Main layout
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        
        # Header bar
        header = Adw.HeaderBar()
        
        # Add profile button
        add_btn = Gtk.Button.new_from_icon_name("list-add-symbolic")
        add_btn.set_tooltip_text("Adicionar Perfil")
        add_btn.connect('clicked', self._on_add_profile)
        header.pack_start(add_btn)
        
        # Menu button
        menu_btn = Gtk.MenuButton()
        menu_btn.set_icon_name("open-menu-symbolic")
        menu_btn.set_tooltip_text("Menu")
        
        # Create menu
        menu = Gtk.PopoverMenu()
        menu_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        menu_box.set_margin_top(8)
        menu_box.set_margin_bottom(8)
        menu_box.set_margin_start(8)
        menu_box.set_margin_end(8)
        
        about_btn = Gtk.Button(label="Sobre")
        about_btn.add_css_class('flat')
        about_btn.connect('clicked', self._on_about)
        menu_box.append(about_btn)
        
        menu.set_child(menu_box)
        menu_btn.set_popover(menu)
        header.pack_end(menu_btn)
        
        main_box.append(header)
        
        # Toast overlay for notifications
        self.toast_overlay = Adw.ToastOverlay()
        self.toast_overlay.set_vexpand(True)
        
        # Main content with paned view
        paned = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)
        paned.set_shrink_start_child(False)
        paned.set_shrink_end_child(False)
        
        # Top section: Profiles
        profiles_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        profiles_box.set_vexpand(True)
        
        # Scrolled window for profiles
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)
        
        # Clamp for max width
        clamp = Adw.Clamp()
        clamp.set_maximum_size(800)
        clamp.set_margin_top(24)
        clamp.set_margin_bottom(24)
        clamp.set_margin_start(12)
        clamp.set_margin_end(12)
        
        # Content box
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        
        # Status banner
        self.status_banner = Adw.Banner()
        self.status_banner.set_title("Desconectado")
        self.status_banner.set_revealed(False)
        content_box.append(self.status_banner)
        
        # Profiles group
        self.profiles_group = Adw.PreferencesGroup()
        self.profiles_group.set_title("Conexões VPN")
        self.profiles_group.set_description("Gerencie seus perfis de conexão VPN")
        content_box.append(self.profiles_group)
        
        # Empty state
        self.empty_status = Adw.StatusPage()
        self.empty_status.set_icon_name("network-vpn-symbolic")
        self.empty_status.set_title("Nenhuma Conexão")
        self.empty_status.set_description("Adicione um perfil VPN para começar")
        
        add_button = Gtk.Button(label="Adicionar Perfil")
        add_button.add_css_class('suggested-action')
        add_button.add_css_class('pill')
        add_button.set_halign(Gtk.Align.CENTER)
        add_button.connect('clicked', self._on_add_profile)
        self.empty_status.set_child(add_button)
        
        content_box.append(self.empty_status)
        
        clamp.set_child(content_box)
        scrolled.set_child(clamp)
        profiles_box.append(scrolled)
        
        paned.set_start_child(profiles_box)
        
        # Bottom section: Logs
        logs_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        logs_box.set_size_request(-1, 150)
        
        # Logs header
        logs_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        logs_header.add_css_class('toolbar')
        logs_header.set_margin_start(12)
        logs_header.set_margin_end(12)
        logs_header.set_margin_top(8)
        logs_header.set_margin_bottom(8)
        
        logs_label = Gtk.Label(label="Logs")
        logs_label.add_css_class('heading')
        logs_header.append(logs_label)
        
        # Spacer
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        logs_header.append(spacer)
        
        # Clear logs button
        clear_btn = Gtk.Button.new_from_icon_name("edit-clear-symbolic")
        clear_btn.set_tooltip_text("Limpar Logs")
        clear_btn.add_css_class('flat')
        clear_btn.connect('clicked', self._on_clear_logs)
        logs_header.append(clear_btn)
        
        logs_box.append(logs_header)
        
        # Separator
        logs_box.append(Gtk.Separator())
        
        # Logs text view
        logs_scrolled = Gtk.ScrolledWindow()
        logs_scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        logs_scrolled.set_vexpand(True)
        
        self.logs_view = Gtk.TextView()
        self.logs_view.set_editable(False)
        self.logs_view.set_cursor_visible(False)
        self.logs_view.set_monospace(True)
        self.logs_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.logs_view.set_left_margin(12)
        self.logs_view.set_right_margin(12)
        self.logs_view.set_top_margin(8)
        self.logs_view.set_bottom_margin(8)
        self.logs_buffer = self.logs_view.get_buffer()
        
        logs_scrolled.set_child(self.logs_view)
        logs_box.append(logs_scrolled)
        
        paned.set_end_child(logs_box)
        paned.set_position(350)
        
        self.toast_overlay.set_child(paned)
        main_box.append(self.toast_overlay)
        
        self.set_content(main_box)
    
    def _load_profiles(self):
        """Load and display profiles."""
        # Clear existing rows
        for profile_id in list(self._profile_rows.keys()):
            row = self._profile_rows.pop(profile_id)
            self.profiles_group.remove(row)
        
        profiles = self.profile_manager.profiles
        
        # Show/hide empty state
        self.empty_status.set_visible(len(profiles) == 0)
        self.profiles_group.set_visible(len(profiles) > 0)
        
        # Add profile rows
        for profile in profiles:
            self._add_profile_row(profile)
        self._on_state_changed(self.vpn_manager, self.vpn_manager.state.value)
    
    def _add_profile_row(self, profile: VPNProfile):
        """Add a profile row to the list."""
        row = ProfileRow(profile)
        row.connect('connect-clicked', self._on_connect_clicked, profile)
        row.connect('edit-clicked', self._on_edit_clicked, profile)
        row.connect('delete-clicked', self._on_delete_clicked, profile)
        
        self.profiles_group.add(row)
        self._profile_rows[profile.id] = row
    
    def _on_add_profile(self, button):
        """Handle add profile button click."""
        dialog = ProfileDialog()
        dialog.connect('profile-saved', self._on_profile_saved)
        dialog.present(self)
    
    def _on_profile_saved(self, dialog, profile):
        """Handle profile save."""
        try:
            self.profile_manager.update(profile)
        except OSError as exc:
            dialog.save_ok = False
            dialog.error_label.set_label(f"Não foi possível salvar o perfil: {exc}")
            dialog.error_label.set_visible(True)
            return
        self._load_profiles()
        
        toast = Adw.Toast(title="Perfil salvo")
        self.toast_overlay.add_toast(toast)
    
    def _on_connect_clicked(self, row, profile):
        """Handle connect button click."""
        current = self.vpn_manager.current_profile
        if current and current.id == profile.id and self.vpn_manager.state in (
                VPNState.CONNECTED, VPNState.CONNECTING):
            self.vpn_manager.disconnect()
        elif self.vpn_manager.state in (VPNState.DISCONNECTED, VPNState.ERROR):
            self.vpn_manager.connect_vpn(profile)
    
    def _on_edit_clicked(self, row, profile):
        """Handle edit button click."""
        dialog = ProfileDialog(profile=profile)
        dialog.connect('profile-saved', self._on_profile_saved)
        dialog.present(self)
    
    def _on_delete_clicked(self, row, profile):
        """Handle delete button click."""
        # Create confirmation dialog
        dialog = Adw.AlertDialog()
        dialog.set_heading("Excluir Perfil?")
        dialog.set_body(f"Tem certeza que deseja excluir o perfil \"{profile.name}\"?")
        dialog.add_response("cancel", "Cancelar")
        dialog.add_response("delete", "Excluir")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        
        dialog.connect('response', self._on_delete_response, profile)
        dialog.present(self)
    
    def _on_delete_response(self, dialog, response, profile):
        """Handle delete confirmation response."""
        if response == "delete":
            current = self.vpn_manager.current_profile
            try:
                self.profile_manager.remove(profile.id)
            except OSError as exc:
                self._on_vpn_error(self.vpn_manager, f"Não foi possível excluir o perfil: {exc}")
                return
            if current and current.id == profile.id:
                self.vpn_manager.disconnect()
            self._load_profiles()
            
            toast = Adw.Toast(title="Perfil excluído")
            self.toast_overlay.add_toast(toast)
    
    def _on_state_changed(self, manager, state_str):
        """Handle VPN state change."""
        state = VPNState(state_str)
        current_profile = manager.current_profile
        
        # Update all rows
        for profile_id, row in self._profile_rows.items():
            is_current = current_profile and current_profile.id == profile_id
            row.set_connection_state(state, is_current)
        
        # Update status banner
        self.status_banner.remove_css_class('error')
        if state == VPNState.CONNECTED and current_profile:
            self.status_banner.set_title(f"Conectado a {current_profile.name}")
            self.status_banner.add_css_class('success')
            self.status_banner.set_revealed(True)
        elif state == VPNState.CONNECTING and current_profile:
            self.status_banner.set_title(f"Conectando a {current_profile.name}...")
            self.status_banner.remove_css_class('success')
            self.status_banner.set_revealed(True)
        elif state == VPNState.DISCONNECTING:
            self.status_banner.set_title("Desconectando...")
            self.status_banner.remove_css_class('success')
            self.status_banner.set_revealed(True)
        elif state == VPNState.ERROR:
            self.status_banner.set_title("Erro na conexão")
            self.status_banner.remove_css_class('success')
            self.status_banner.add_css_class('error')
            self.status_banner.set_revealed(True)
        else:
            self.status_banner.set_revealed(False)
            self.status_banner.remove_css_class('success')
            self.status_banner.remove_css_class('error')
    
    def _on_log_message(self, manager, message):
        """Handle log message."""
        end_iter = self.logs_buffer.get_end_iter()
        self.logs_buffer.insert(end_iter, f"{message}\n")
        
        # Auto-scroll to bottom
        GLib.idle_add(self._scroll_logs_to_bottom)
    
    def _scroll_logs_to_bottom(self):
        """Scroll logs to bottom."""
        adj = self.logs_view.get_parent().get_vadjustment()
        adj.set_value(adj.get_upper())
    
    def _on_vpn_error(self, manager, message):
        """Handle VPN error."""
        toast = Adw.Toast(title=f"Erro: {message}")
        toast.set_timeout(5)
        self.toast_overlay.add_toast(toast)
    
    def _on_otp_required(self, manager):
        """Handle OTP request."""
        self._show_secret_dialog("Autenticação de Dois Fatores", "Digite o código 2FA:", False)

    def _on_password_required(self, manager):
        self._show_secret_dialog("Senha da VPN", "Digite a senha da VPN:", True)

    def _show_secret_dialog(self, title, prompt, hidden):
        if self.vpn_manager.state not in (VPNState.CONNECTING, VPNState.CONNECTED):
            return
        # Create a simple dialog for OTP input
        # Since we want to be compatible with GTK4/Adwaita, we use a modal window
        dialog = Gtk.Window(transient_for=self, modal=True)
        dialog.set_title(title)
        dialog.set_default_size(300, 150)
        dialog.set_resizable(False)
        
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)
        
        label = Gtk.Label(label=prompt)
        box.append(label)
        
        entry = Gtk.Entry()
        entry.set_visibility(not hidden)
        entry.set_placeholder_text("Senha" if hidden else "123456")
        entry.set_alignment(0.5)
        entry.connect('activate', lambda w: self._on_secret_submit(dialog, entry, hidden))
        box.append(entry)
        
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        btn_box.set_halign(Gtk.Align.CENTER)
        
        cancel_btn = Gtk.Button(label="Cancelar")
        cancel_btn.connect('clicked', lambda w: (dialog.close(), self.vpn_manager.disconnect()))
        
        ok_btn = Gtk.Button(label="Confirmar")
        ok_btn.add_css_class('suggested-action')
        ok_btn.connect('clicked', lambda w: self._on_secret_submit(dialog, entry, hidden))
        
        btn_box.append(cancel_btn)
        btn_box.append(ok_btn)
        box.append(btn_box)
        
        dialog.set_child(box)
        dialog.present()
        entry.grab_focus()
        
    def _on_secret_submit(self, dialog, entry, hidden):
        """Submit a password or OTP without changing password whitespace."""
        value = entry.get_text() if hidden else entry.get_text().strip()
        if value:
            self.vpn_manager.send_input(value)
            dialog.close()
    
    def _on_clear_logs(self, button):
        """Clear logs."""
        self.logs_buffer.set_text("")
    
    def _on_about(self, button):
        """Show about dialog."""
        about = Adw.AboutDialog()
        about.set_application_name("OpenFortiVPN GTK")
        about.set_version("1.0.0")
        about.set_developer_name("OpenFortiVPN GTK Contributors")
        about.set_license_type(Gtk.License.GPL_3_0)
        about.set_comments("Uma interface gráfica moderna para o OpenFortiVPN")
        about.set_website("https://github.com/adrienverge/openfortivpn")
        about.set_application_icon("openfortivpn-gtk")
        about.present(self)

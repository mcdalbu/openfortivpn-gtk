"""GTK4 tray integration through StatusNotifierItem and DBusMenu.

Uses the existing Gio session bus, without loading GTK3 into the GTK4 app.
Protocol reference: https://api.kde.org/kstatusnotifieritem.html
"""

import html
from pathlib import Path

import gi
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Gio, GLib, GdkPixbuf


WATCHER = 'org.kde.StatusNotifierWatcher'
WATCHER_PATH = '/StatusNotifierWatcher'
ITEM_INTERFACE = 'org.kde.StatusNotifierItem'
ITEM_PATH = '/StatusNotifierItem'
MENU_INTERFACE = 'com.canonical.dbusmenu'
MENU_PATH = '/MenuBar'

ITEM_XML = '''<node><interface name="org.kde.StatusNotifierItem">
<property name="Category" type="s" access="read"/>
<property name="Id" type="s" access="read"/>
<property name="Title" type="s" access="read"/>
<property name="Status" type="s" access="read"/>
<property name="WindowId" type="i" access="read"/>
<property name="IconThemePath" type="s" access="read"/>
<property name="IconName" type="s" access="read"/>
<property name="IconPixmap" type="a(iiay)" access="read"/>
<property name="OverlayIconName" type="s" access="read"/>
<property name="OverlayIconPixmap" type="a(iiay)" access="read"/>
<property name="AttentionIconName" type="s" access="read"/>
<property name="AttentionIconPixmap" type="a(iiay)" access="read"/>
<property name="AttentionMovieName" type="s" access="read"/>
<property name="ToolTip" type="(sa(iiay)ss)" access="read"/>
<property name="ItemIsMenu" type="b" access="read"/>
<property name="Menu" type="o" access="read"/>
<method name="Activate"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
<method name="SecondaryActivate"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
<method name="ContextMenu"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
<method name="Scroll"><arg type="i" direction="in"/><arg type="s" direction="in"/></method>
<method name="ProvideXdgActivationToken"><arg type="s" direction="in"/></method>
<signal name="NewTitle"/><signal name="NewIcon"/><signal name="NewToolTip"/>
<signal name="NewStatus"><arg type="s"/></signal>
</interface></node>'''

MENU_XML = '''<node><interface name="com.canonical.dbusmenu">
<property name="Version" type="u" access="read"/>
<property name="TextDirection" type="s" access="read"/>
<property name="Status" type="s" access="read"/>
<property name="IconThemePath" type="as" access="read"/>
<method name="GetLayout">
<arg type="i" direction="in"/><arg type="i" direction="in"/><arg type="as" direction="in"/>
<arg type="u" direction="out"/><arg type="(ia{sv}av)" direction="out"/>
</method>
<method name="GetGroupProperties">
<arg type="ai" direction="in"/><arg type="as" direction="in"/><arg type="a(ia{sv})" direction="out"/>
</method>
<method name="GetProperty">
<arg type="i" direction="in"/><arg type="s" direction="in"/><arg type="v" direction="out"/>
</method>
<method name="Event">
<arg type="i" direction="in"/><arg type="s" direction="in"/><arg type="v" direction="in"/><arg type="u" direction="in"/>
</method>
<method name="EventGroup"><arg type="a(isvu)" direction="in"/><arg type="ai" direction="out"/></method>
<method name="AboutToShow"><arg type="i" direction="in"/><arg type="b" direction="out"/></method>
<method name="AboutToShowGroup">
<arg type="ai" direction="in"/><arg type="ai" direction="out"/><arg type="ai" direction="out"/>
</method>
<signal name="LayoutUpdated"><arg type="u"/><arg type="i"/></signal>
<signal name="ItemsPropertiesUpdated"><arg type="a(ia{sv})"/><arg type="a(ias)"/></signal>
</interface></node>'''


class TrayIndicator:
    def __init__(self, on_show, on_disconnect, on_quit, on_available):
        self.actions = {1: on_show, 3: on_disconnect, 5: on_quit}
        self.on_available = on_available
        self.available = False
        self._availability_reported = False
        self.connection = None
        self._objects = []
        self._subscriptions = []
        self._watch_id = 0
        self._owner = None
        self._generation = 0
        self._registered = False
        self._host = False
        self._stopped = False
        self._cancellable = Gio.Cancellable()
        self._revision = 1
        self.status_text = 'Desconectado'
        self.can_disconnect = False
        self.icon_path = self._find_icon()
        self._pixmaps = self._load_pixmaps()
        self.error = None
        self.activation_token = None

    @staticmethod
    def _find_icon():
        candidates = (Path(__file__).resolve().parent.parent / 'data' / 'openfortivpn-gtk.png',
                      Path('/usr/share/icons/hicolor/128x128/apps/openfortivpn-gtk.png'),
                      Path.home() / '.local/share/icons/hicolor/128x128/apps/openfortivpn-gtk.png')
        return next((path for path in candidates if path.is_file()), None)

    def _load_pixmaps(self):
        if not self.icon_path:
            return []
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(self.icon_path), 64, 64, True)
            pixels = pixbuf.get_pixels()
            argb = bytearray()
            channels, stride = pixbuf.get_n_channels(), pixbuf.get_rowstride()
            for y in range(pixbuf.get_height()):
                for x in range(pixbuf.get_width()):
                    offset = y * stride + x * channels
                    red, green, blue = pixels[offset:offset + 3]
                    alpha = pixels[offset + 3] if channels == 4 else 255
                    argb.extend((alpha, red, green, blue))
            return [(pixbuf.get_width(), pixbuf.get_height(), bytes(argb))]
        except GLib.Error:
            return []

    def start(self, connection=None):
        if connection is not None:
            self._export(connection)
        else:
            Gio.bus_get(Gio.BusType.SESSION, self._cancellable, self._bus_ready)

    def _bus_ready(self, source, result):
        try:
            connection = Gio.bus_get_finish(result)
            if not self._stopped:
                self._export(connection)
        except GLib.Error as exc:
            self.error = str(exc)
            self._set_available()

    def _export(self, connection):
        self.connection = connection
        try:
            for path, xml, method, getter in (
                    (ITEM_PATH, ITEM_XML, self._item_method, self._item_property),
                    (MENU_PATH, MENU_XML, self._menu_method, self._menu_property)):
                interface = Gio.DBusNodeInfo.new_for_xml(xml).interfaces[0]
                self._objects.append(connection.register_object(path, interface, method, getter, None))
            self._watch_id = Gio.bus_watch_name_on_connection(
                connection, WATCHER, Gio.BusNameWatcherFlags.NONE,
                self._watcher_appeared, self._watcher_vanished)
            for interface, signal_name in ((WATCHER, None),
                                            ('org.freedesktop.DBus.Properties', 'PropertiesChanged')):
                self._subscriptions.append(connection.signal_subscribe(
                    WATCHER, interface, signal_name, WATCHER_PATH, None,
                    Gio.DBusSignalFlags.NONE, self._watcher_signal))
        except GLib.Error as exc:
            self.error = str(exc)
            self.stop()

    def _set_available(self):
        value = bool(self._owner and self._registered and self._host and not self._stopped)
        if value != self.available or not self._availability_reported:
            self.available = value
            self._availability_reported = True
            self.on_available(value)

    def _watcher_appeared(self, connection, name, owner):
        self._generation += 1
        self._owner = owner
        self._registered = self._host = False
        self._set_available()
        connection.call(owner, WATCHER_PATH, WATCHER, 'RegisterStatusNotifierItem',
                        GLib.Variant('(s)', (ITEM_PATH,)), None,
                        Gio.DBusCallFlags.NONE, 5000, self._cancellable,
                        self._registered_reply, self._generation)
        self._check_host()

    def _registered_reply(self, connection, result, generation):
        try:
            connection.call_finish(result)
        except GLib.Error as exc:
            if generation == self._generation:
                self.error = str(exc)
            return
        if generation == self._generation and not self._stopped:
            self._registered = True
            self._set_available()

    def _check_host(self):
        if self._owner and not self._stopped:
            self.connection.call(
                self._owner, WATCHER_PATH, 'org.freedesktop.DBus.Properties', 'Get',
                GLib.Variant('(ss)', (WATCHER, 'IsStatusNotifierHostRegistered')),
                GLib.VariantType.new('(v)'), Gio.DBusCallFlags.NONE, 5000,
                self._cancellable, self._host_reply, self._generation)

    def _host_reply(self, connection, result, generation):
        try:
            reply = connection.call_finish(result)
            host = reply.get_child_value(0).get_variant().get_boolean()
        except GLib.Error:
            host = False
        if generation == self._generation and not self._stopped:
            self._host = host
            self._set_available()

    def _watcher_signal(self, connection, sender, path, interface, signal_name, parameters):
        if signal_name in ('StatusNotifierHostRegistered', 'StatusNotifierHostUnregistered', 'PropertiesChanged'):
            self._check_host()

    def _watcher_vanished(self, connection, name):
        self._generation += 1
        self._owner = None
        self._registered = self._host = False
        self._set_available()

    def _item_property(self, connection, sender, path, interface, name):
        properties = {
            'Category': GLib.Variant('s', 'Communications'),
            'Id': GLib.Variant('s', 'openfortivpn-gtk'),
            'Title': GLib.Variant('s', 'OpenFortiVPN'),
            'Status': GLib.Variant('s', 'Active'),
            'WindowId': GLib.Variant('i', 0),
            'IconThemePath': GLib.Variant('s', str(self.icon_path.parent) if self.icon_path else ''),
            'IconName': GLib.Variant('s', 'openfortivpn-gtk'),
            'IconPixmap': GLib.Variant('a(iiay)', self._pixmaps),
            'OverlayIconName': GLib.Variant('s', ''),
            'OverlayIconPixmap': GLib.Variant('a(iiay)', []),
            'AttentionIconName': GLib.Variant('s', 'openfortivpn-gtk'),
            'AttentionIconPixmap': GLib.Variant('a(iiay)', self._pixmaps),
            'AttentionMovieName': GLib.Variant('s', ''),
            'ToolTip': GLib.Variant('(sa(iiay)ss)', ('openfortivpn-gtk', [], 'OpenFortiVPN', html.escape(self.status_text))),
            'ItemIsMenu': GLib.Variant('b', False),
            'Menu': GLib.Variant('o', MENU_PATH),
        }
        return properties.get(name)

    def _item_method(self, connection, sender, path, interface, method, parameters, invocation):
        if method == 'ProvideXdgActivationToken':
            self.activation_token = parameters.unpack()[0]
        invocation.return_value(None)
        if method in ('Activate', 'SecondaryActivate', 'ContextMenu'):
            GLib.idle_add(self._dispatch, 1, 'clicked')

    @staticmethod
    def _menu_property(connection, sender, path, interface, name):
        return {'Version': GLib.Variant('u', 3), 'TextDirection': GLib.Variant('s', 'ltr'),
                'Status': GLib.Variant('s', 'normal'), 'IconThemePath': GLib.Variant('as', [])}.get(name)

    def _menu_items(self):
        return {
            0: {'children-display': GLib.Variant('s', 'submenu')},
            1: {'label': GLib.Variant('s', 'Abrir OpenFortiVPN')},
            2: {'label': GLib.Variant('s', self.status_text.replace('_', '__')), 'enabled': GLib.Variant('b', False)},
            3: {'label': GLib.Variant('s', 'Desconectar'), 'enabled': GLib.Variant('b', self.can_disconnect)},
            4: {'type': GLib.Variant('s', 'separator')},
            5: {'label': GLib.Variant('s', 'Sair')},
        }

    def _dispatch(self, item_id, event):
        if not self._stopped and event == 'clicked' and item_id in self.actions:
            if item_id != 3 or self.can_disconnect:
                self.actions[item_id]()
        return GLib.SOURCE_REMOVE

    def _menu_method(self, connection, sender, path, interface, method, parameters, invocation):
        args = parameters.unpack()
        items = self._menu_items()
        try:
            if method == 'GetLayout':
                item_id, depth, names = args
                properties = {key: value for key, value in items[item_id].items() if not names or key in names}
                children = []
                if item_id == 0 and depth != 0:
                    for child_id in range(1, 6):
                        props = {key: value for key, value in items[child_id].items() if not names or key in names}
                        children.append(GLib.Variant('(ia{sv}av)', (child_id, props, [])))
                reply = GLib.Variant('(u(ia{sv}av))', (self._revision, (item_id, properties, children)))
            elif method == 'GetGroupProperties':
                ids, names = args
                values = [(key, {name: value for name, value in items[key].items() if not names or name in names})
                          for key in (ids or list(items)) if key in items]
                reply = GLib.Variant('(a(ia{sv}))', (values,))
            elif method == 'GetProperty':
                reply = GLib.Variant('(v)', (items[args[0]][args[1]],))
            elif method == 'Event':
                invocation.return_value(None)
                GLib.idle_add(self._dispatch, args[0], args[1])
                return
            elif method == 'EventGroup':
                errors = [event[0] for event in args[0] if event[0] not in items]
                reply = GLib.Variant('(ai)', (errors,))
                for event in args[0]:
                    GLib.idle_add(self._dispatch, event[0], event[1])
            elif method == 'AboutToShow':
                reply = GLib.Variant('(b)', (False,))
            elif method == 'AboutToShowGroup':
                reply = GLib.Variant('(aiai)', ([], [item_id for item_id in args[0] if item_id not in items]))
            else:
                invocation.return_dbus_error('org.freedesktop.DBus.Error.UnknownMethod', method)
                return
            invocation.return_value(reply)
        except KeyError:
            invocation.return_dbus_error('com.canonical.dbusmenu.Error.InvalidMenuItem', 'Item inexistente')

    def update(self, state, profile=None):
        labels = {'disconnected': 'Desconectado', 'connecting': 'Conectando',
                  'connected': 'Conectado', 'disconnecting': 'Desconectando', 'error': 'Erro na conexão'}
        self.status_text = labels[state]
        if profile and state in ('connected', 'connecting'):
            self.status_text += f' · {profile.name}'
        self.can_disconnect = state in ('connecting', 'connected')
        self._revision += 1
        if self.connection and not self._stopped:
            self.connection.emit_signal(None, MENU_PATH, MENU_INTERFACE, 'LayoutUpdated',
                                        GLib.Variant('(ui)', (self._revision, 0)))
            self.connection.emit_signal(None, ITEM_PATH, ITEM_INTERFACE, 'NewToolTip', None)

    def stop(self):
        self._stopped = True
        self._cancellable.cancel()
        if self._watch_id:
            Gio.bus_unwatch_name(self._watch_id)
            self._watch_id = 0
        if self.connection:
            for subscription in self._subscriptions:
                self.connection.signal_unsubscribe(subscription)
            for registration in self._objects:
                self.connection.unregister_object(registration)
        self._subscriptions.clear()
        self._objects.clear()
        self._set_available()

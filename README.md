# OpenFortiVPN GTK

A modern GTK4/libadwaita interface for OpenFortiVPN.

## Requirements

- Python 3.10+
- GTK 4
- libadwaita
- openfortivpn
- pkexec (polkit) to authorize the connection
- setsid (util-linux) to control the VPN terminal

### Installing dependencies on Debian/Ubuntu:

```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1 openfortivpn
```

### Installing dependencies on Fedora:

```bash
sudo dnf install python3-gobject gtk4 libadwaita openfortivpn
```

### Installing dependencies on Arch Linux:

```bash
sudo pacman -S python-gobject gtk4 libadwaita openfortivpn
```

## Running

```bash
python3 -m openfortivpn_gtk
```

Prebuilt RPMs are available on the
[GitHub releases page](https://github.com/mcdalbu/openfortivpn-gtk/releases/latest).
Download the `noarch.rpm` package and install it with `sudo dnf install`
followed by the downloaded file's path.

To install the app and icon in the application menu from source, use `sudo ./install.sh`
on traditional distributions or `./install-atomic.sh` on atomic systems.

On Fedora, build and install the RPM with:

```bash
./build-rpm.sh
sudo dnf install ./dist/openfortivpn-gtk-1.0.0-1.fc44.noarch.rpm
```

The build requires `rpm-build`, `desktop-file-utils`, and the application
dependencies listed above. Binary and source RPMs are written to `dist/`.
On rpm-ostree systems, install the binary RPM with `sudo rpm-ostree install`
and reboot into the new deployment.

Profiles are stored in `~/.config/openfortivpn-gtk/profiles.json` with access
restricted to your user. Passwords are stored in this file. Leave the password
field empty to enter it when the server asks for it.

Run the tests with:

```bash
/usr/bin/python3 -m unittest discover -s tests -v
```

## Features

- 🔐 Manage multiple VPN profiles
- 🔌 One-click connect/disconnect
- 📋 Real-time connection logs
- 🌙 Dark/light theme support (follows system)
- 💾 Profiles saved locally in JSON format

## License

GPL-3.0 (same as openfortivpn)

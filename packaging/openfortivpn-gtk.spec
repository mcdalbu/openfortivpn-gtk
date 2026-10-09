%global __brp_python_bytecompile %{nil}

Name:           openfortivpn-gtk
Version:        1.0.0
Release:        1%{?dist}
Summary:        GTK interface for managing OpenFortiVPN connections
License:        GPL-3.0-only
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch

BuildRequires:  python3 >= 3.10
BuildRequires:  python3-gobject
BuildRequires:  gtk4
BuildRequires:  libadwaita >= 1.5
BuildRequires:  desktop-file-utils
BuildRequires:  /usr/bin/setsid

Requires:       python3 >= 3.10
Requires:       python3-gobject
Requires:       gtk4
Requires:       libadwaita >= 1.5
Requires:       openfortivpn
Requires:       /usr/bin/pkexec
Requires:       /usr/bin/setsid

%description
A GTK4 and libadwaita application for managing OpenFortiVPN profiles,
connecting to Fortinet VPN gateways, and viewing connection logs.

%prep
%autosetup

%build
# The application is distributed as Python source.

%install
install -d %{buildroot}%{_datadir}/%{name}
cp -r openfortivpn_gtk %{buildroot}%{_datadir}/%{name}/

install -D -m 0755 packaging/launcher.py %{buildroot}%{_bindir}/%{name}
sed -i 's|@APPDIR@|%{_datadir}/%{name}|g' %{buildroot}%{_bindir}/%{name}

install -D -m 0644 data/openfortivpn-gtk.desktop \
    %{buildroot}%{_datadir}/applications/com.github.openfortivpn.gtk.desktop
install -D -m 0644 data/openfortivpn-gtk.svg \
    %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/%{name}.svg
install -D -m 0644 data/openfortivpn-gtk.png \
    %{buildroot}%{_datadir}/icons/hicolor/128x128/apps/%{name}.png

%check
desktop-file-validate %{buildroot}%{_datadir}/applications/com.github.openfortivpn.gtk.desktop
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest discover -s tests -v

%files
%license LICENSE
%doc README.md
%{_bindir}/%{name}
%{_datadir}/%{name}/
%{_datadir}/applications/com.github.openfortivpn.gtk.desktop
%{_datadir}/icons/hicolor/scalable/apps/%{name}.svg
%{_datadir}/icons/hicolor/128x128/apps/%{name}.png

%changelog
* Fri Oct 09 2026 OpenFortiVPN GTK Contributors - 1.0.0-1
- Package the reviewed application and its new icon.

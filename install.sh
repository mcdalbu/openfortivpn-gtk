#!/bin/bash
#
# OpenFortiVPN GTK - Installation Script
# 
# This script installs the OpenFortiVPN GTK application
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Installation paths
INSTALL_DIR="/opt/openfortivpn-gtk"
BIN_LINK="/usr/local/bin/openfortivpn-gtk"
DESKTOP_FILE="/usr/share/applications/openfortivpn-gtk.desktop"
ICON_DIR="/usr/share/icons/hicolor/scalable/apps"
ICON_PNG_DIR="/usr/share/icons/hicolor/128x128/apps"

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${BLUE}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║           OpenFortiVPN GTK - Instalador                      ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        echo -e "${YELLOW}Este script precisa de permissões de administrador.${NC}"
        echo -e "${YELLOW}Por favor, execute com sudo.${NC}"
        exit 1
    fi
}

# Detect distribution
detect_distro() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        DISTRO=$ID
        DISTRO_LIKE=$ID_LIKE
    elif [ -f /etc/lsb-release ]; then
        . /etc/lsb-release
        DISTRO=$DISTRIB_ID
    else
        DISTRO="unknown"
    fi
    echo -e "${BLUE}Distribuição detectada:${NC} $DISTRO"
}

# Install dependencies based on distribution
install_dependencies() {
    echo -e "\n${BLUE}Instalando dependências...${NC}\n"
    
    case $DISTRO in
        ubuntu|debian|linuxmint|pop)
            apt-get update
            apt-get install -y python3 python3-gi python3-gi-cairo \
                gir1.2-gtk-4.0 gir1.2-adw-1 openfortivpn
            ;;
        fedora)
            dnf install -y python3 python3-gobject gtk4 libadwaita openfortivpn
            ;;
        arch|manjaro|endeavouros)
            pacman -S --noconfirm python python-gobject gtk4 libadwaita openfortivpn
            ;;
        opensuse*|suse)
            zypper install -y python3 python3-gobject gtk4 libadwaita-1-0 openfortivpn
            ;;
        *)
            # Check if distro is based on another
            if [[ "$DISTRO_LIKE" == *"debian"* ]] || [[ "$DISTRO_LIKE" == *"ubuntu"* ]]; then
                apt-get update
                apt-get install -y python3 python3-gi python3-gi-cairo \
                    gir1.2-gtk-4.0 gir1.2-adw-1 openfortivpn
            elif [[ "$DISTRO_LIKE" == *"fedora"* ]] || [[ "$DISTRO_LIKE" == *"rhel"* ]]; then
                dnf install -y python3 python3-gobject gtk4 libadwaita openfortivpn
            elif [[ "$DISTRO_LIKE" == *"arch"* ]]; then
                pacman -S --noconfirm python python-gobject gtk4 libadwaita openfortivpn
            else
                echo -e "${YELLOW}Distribuição não reconhecida. Instale manualmente:${NC}"
                echo "  - python3"
                echo "  - python3-gi / python-gobject"
                echo "  - gtk4"
                echo "  - libadwaita"
                echo "  - openfortivpn"
                read -p "Continuar mesmo assim? [s/N] " -n 1 -r
                echo
                if [[ ! $REPLY =~ ^[Ss]$ ]]; then
                    exit 1
                fi
            fi
            ;;
    esac
    
    echo -e "${GREEN}✓ Dependências instaladas${NC}"
}

# Verify dependencies are working
verify_dependencies() {
    echo -e "\n${BLUE}Verificando dependências...${NC}"
    
    # Check Python
    if [ ! -f /usr/bin/python3 ]; then
        echo -e "${RED}✗ Python3 do sistema (/usr/bin/python3) não encontrado${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Python3 $(/usr/bin/python3 --version | cut -d' ' -f2)${NC}"
    
    # Check GTK4 and libadwaita
    if /usr/bin/python3 -c "import gi; gi.require_version('Gtk', '4.0'); gi.require_version('Adw', '1')" 2>/dev/null; then
        echo -e "${GREEN}✓ GTK4 e libadwaita disponíveis${NC}"
    else
        echo -e "${RED}✗ GTK4 ou libadwaita não encontrados${NC}"
        exit 1
    fi
    
    # Check openfortivpn
    if command -v openfortivpn &> /dev/null; then
        echo -e "${GREEN}✓ openfortivpn $(openfortivpn --version 2>&1 | head -n1)${NC}"
    else
        echo -e "${YELLOW}⚠ openfortivpn não encontrado no PATH${NC}"
        echo -e "${YELLOW}  Você precisará instalá-lo separadamente${NC}"
    fi
}

# Install the application
install_app() {
    echo -e "\n${BLUE}Instalando aplicação...${NC}"
    
    # Create installation directory
    mkdir -p "$INSTALL_DIR"
    
    # Copy application files
    cp -r "$SCRIPT_DIR/openfortivpn_gtk" "$INSTALL_DIR/"
    
    # Create launcher script
    cat > "$INSTALL_DIR/launch.sh" << 'EOF'
#!/bin/bash
cd /opt/openfortivpn-gtk
exec /usr/bin/python3 -m openfortivpn_gtk "$@"
EOF
    chmod +x "$INSTALL_DIR/launch.sh"
    
    # Create symlink in /usr/local/bin
    ln -sf "$INSTALL_DIR/launch.sh" "$BIN_LINK"
    
    echo -e "${GREEN}✓ Aplicação instalada em $INSTALL_DIR${NC}"
}

# Install desktop file
install_desktop() {
    echo -e "\n${BLUE}Instalando entrada de menu...${NC}"
    
    # Create desktop file
    cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Name=OpenFortiVPN
GenericName=VPN Client
Comment=Interface gráfica para OpenFortiVPN
Exec=$BIN_LINK
Icon=openfortivpn-gtk
Terminal=false
Type=Application
Categories=Network;GTK;
Keywords=vpn;fortinet;fortigate;openfortivpn;
StartupNotify=true
StartupWMClass=openfortivpn-gtk
EOF
    
    mkdir -p "$ICON_DIR" "$ICON_PNG_DIR"
    cp "$SCRIPT_DIR/data/openfortivpn-gtk.svg" "$ICON_DIR/openfortivpn-gtk.svg"
    cp "$SCRIPT_DIR/data/openfortivpn-gtk.png" "$ICON_PNG_DIR/openfortivpn-gtk.png"
    
    # Update desktop database
    if command -v update-desktop-database &> /dev/null; then
        update-desktop-database /usr/share/applications/ 2>/dev/null || true
    fi
    
    echo -e "${GREEN}✓ Entrada de menu criada${NC}"
}

# Print completion message
print_success() {
    echo -e "\n${GREEN}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║               Instalação concluída com sucesso!              ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo -e "Você pode executar a aplicação de duas formas:"
    echo -e ""
    echo -e "  ${BLUE}1. Pelo terminal:${NC}"
    echo -e "     openfortivpn-gtk"
    echo -e ""
    echo -e "  ${BLUE}2. Pelo menu de aplicações:${NC}"
    echo -e "     Procure por 'OpenFortiVPN'"
    echo -e ""
}

# Uninstall function
uninstall() {
    echo -e "${YELLOW}Desinstalando OpenFortiVPN GTK...${NC}"
    
    rm -rf "$INSTALL_DIR"
    rm -f "$BIN_LINK"
    rm -f "$DESKTOP_FILE"
    rm -f "/usr/share/polkit-1/actions/com.github.openfortivpn.gtk.policy"
    rm -f "$ICON_DIR/openfortivpn-gtk.svg" "$ICON_PNG_DIR/openfortivpn-gtk.png"
    
    if command -v update-desktop-database &> /dev/null; then
        update-desktop-database /usr/share/applications/ 2>/dev/null || true
    fi
    
    echo -e "${GREEN}✓ OpenFortiVPN GTK foi removido${NC}"
}

# Main installation flow
main() {
    # Check for uninstall flag
    if [[ "$1" == "--uninstall" ]] || [[ "$1" == "-u" ]]; then
        check_root
        uninstall
        exit 0
    fi
    
    # Check for help flag
    if [[ "$1" == "--help" ]] || [[ "$1" == "-h" ]]; then
        echo "Uso: $0 [opções]"
        echo ""
        echo "Opções:"
        echo "  --help, -h        Mostra esta ajuda"
        echo "  --uninstall, -u   Remove a aplicação"
        echo "  --no-deps         Pula instalação de dependências"
        echo ""
        exit 0
    fi
    
    check_root
    detect_distro
    
    # Install dependencies unless --no-deps is passed
    if [[ "$1" != "--no-deps" ]]; then
        install_dependencies
    fi
    
    verify_dependencies
    install_app
    install_desktop
    print_success
}

# Run main
main "$@"

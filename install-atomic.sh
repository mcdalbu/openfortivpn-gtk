#!/bin/bash
#
# OpenFortiVPN GTK - Instalador para Sistemas Atômicos
# 
# Compatível com: Fedora Silverblue, Kinoite, Bazzite, 
#                 Universal Blue, VanillaOS, etc.
#
# Este script instala a aplicação no diretório do usuário ($HOME/.local)
# já que o sistema de arquivos raiz é imutável.
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Installation paths (user-local)
INSTALL_DIR="$HOME/.local/share/openfortivpn-gtk"
BIN_DIR="$HOME/.local/bin"
BIN_LINK="$BIN_DIR/openfortivpn-gtk"
DESKTOP_DIR="$HOME/.local/share/applications"
DESKTOP_FILE="$DESKTOP_DIR/openfortivpn-gtk.desktop"
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
ICON_PNG_DIR="$HOME/.local/share/icons/hicolor/128x128/apps"

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     OpenFortiVPN GTK - Instalador para Sistemas Atômicos     ║"
echo "║                                                              ║"
echo "║   Fedora Silverblue • Kinoite • Bazzite • Universal Blue     ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Detect if running on an atomic system
detect_atomic() {
    if command -v rpm-ostree &> /dev/null; then
        echo -e "${GREEN}✓ Sistema atômico detectado (rpm-ostree)${NC}"
        ATOMIC_TYPE="rpm-ostree"
        return 0
    elif [ -f /run/ostree-booted ]; then
        echo -e "${GREEN}✓ Sistema OSTree detectado${NC}"
        ATOMIC_TYPE="ostree"
        return 0
    else
        echo -e "${YELLOW}⚠ Este não parece ser um sistema atômico${NC}"
        echo -e "${YELLOW}  Considere usar o install.sh padrão${NC}"
        read -p "Continuar mesmo assim? [s/N] " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Ss]$ ]]; then
            exit 1
        fi
        ATOMIC_TYPE="unknown"
    fi
}

# Check for required tools
check_requirements() {
    echo -e "\n${BLUE}Verificando requisitos...${NC}"
    
    local missing=()
    
    # Check Python
    if [ ! -f /usr/bin/python3 ]; then
        missing+=("python3")
    else
        echo -e "${GREEN}✓ Python3 $(/usr/bin/python3 --version | cut -d' ' -f2)${NC}"
    fi
    
    # Check GTK4 and libadwaita via Python
    if /usr/bin/python3 -c "import gi; gi.require_version('Gtk', '4.0'); gi.require_version('Adw', '1')" 2>/dev/null; then
        echo -e "${GREEN}✓ GTK4 e libadwaita disponíveis${NC}"
    else
        missing+=("gtk4" "libadwaita" "python3-gobject")
    fi
    
    # Check openfortivpn
    if command -v openfortivpn &> /dev/null; then
        echo -e "${GREEN}✓ openfortivpn disponível${NC}"
    else
        missing+=("openfortivpn")
    fi
    
    if [ ${#missing[@]} -gt 0 ]; then
        echo -e "\n${YELLOW}⚠ Dependências faltando: ${missing[*]}${NC}"
        install_dependencies_atomic "${missing[@]}"
    fi
}

# Install dependencies on atomic systems
install_dependencies_atomic() {
    local deps=("$@")
    
    echo -e "\n${BLUE}Instalando dependências no sistema atômico...${NC}"
    echo -e "${YELLOW}Nota: Em sistemas atômicos, algumas dependências podem${NC}"
    echo -e "${YELLOW}      requerer reinicialização após instalação.${NC}\n"
    
    # Check if Flatpak runtime is available
    if flatpak list 2>/dev/null | grep -q "org.gnome.Platform"; then
        echo -e "${GREEN}✓ GNOME Platform Flatpak disponível${NC}"
    fi
    
    # Option 1: rpm-ostree (requires reboot)
    echo -e "\n${BLUE}Opções de instalação:${NC}\n"
    echo "1) rpm-ostree install (requer reinicialização)"
    echo "2) Usar Distrobox/Toolbox (container)"
    echo "3) Pular (já tenho as dependências)"
    echo ""
    read -p "Escolha [1-3]: " choice
    
    case $choice in
        1)
            install_via_rpm_ostree
            ;;
        2)
            install_via_distrobox
            ;;
        3)
            echo -e "${YELLOW}Pulando instalação de dependências...${NC}"
            ;;
        *)
            echo -e "${RED}Opção inválida${NC}"
            exit 1
            ;;
    esac
}

# Install via rpm-ostree
install_via_rpm_ostree() {
    echo -e "\n${BLUE}Instalando via rpm-ostree...${NC}"
    echo -e "${YELLOW}Isso adicionará pacotes à próxima implantação do sistema.${NC}\n"
    
    # Check which packages are actually missing
    local packages_to_install=()
    
    # Check openfortivpn specifically (the most likely missing one)
    if ! command -v openfortivpn &> /dev/null; then
        packages_to_install+=("openfortivpn")
    fi
    
    # Check if GTK4/libadwaita Python bindings work
    if ! /usr/bin/python3 -c "import gi; gi.require_version('Gtk', '4.0'); gi.require_version('Adw', '1')" 2>/dev/null; then
        packages_to_install+=("python3-gobject" "gtk4" "libadwaita")
    fi
    
    if [ ${#packages_to_install[@]} -eq 0 ]; then
        echo -e "${GREEN}✓ Todas as dependências já estão instaladas!${NC}"
        return 0
    fi
    
    echo "Pacotes a instalar: ${packages_to_install[*]}"
    read -p "Continuar? [s/N] " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Ss]$ ]]; then
        # Use --idempotent to avoid errors with already-installed packages
        rpm-ostree install --idempotent "${packages_to_install[@]}"
        
        echo -e "\n${YELLOW}╔══════════════════════════════════════════════════════════════╗"
        echo -e "║  ATENÇÃO: Reinicialização necessária!                         ║"
        echo -e "║                                                                ║"
        echo -e "║  Execute: systemctl reboot                                    ║"
        echo -e "║                                                                ║"
        echo -e "║  Após reiniciar, execute este script novamente.               ║"
        echo -e "╚══════════════════════════════════════════════════════════════╝${NC}"
        
        read -p "Reiniciar agora? [s/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Ss]$ ]]; then
            systemctl reboot
        fi
        exit 0
    fi
}

# Install via Distrobox
install_via_distrobox() {
    echo -e "\n${BLUE}Configurando via Distrobox...${NC}"
    
    local container_name="openfortivpn-gtk"
    
    # Check if distrobox is available
    if ! command -v distrobox &> /dev/null; then
        echo -e "${YELLOW}Distrobox não encontrado. Instalando...${NC}"
        curl -s https://raw.githubusercontent.com/89luca89/distrobox/main/install | sh -s -- --prefix ~/.local
        export PATH="$HOME/.local/bin:$PATH"
    fi
    
    # Create container
    echo -e "${BLUE}Criando container Fedora...${NC}"
    distrobox create --name "$container_name" --image fedora:latest --yes || true
    
    # Install dependencies inside container
    echo -e "${BLUE}Instalando dependências no container...${NC}"
    distrobox enter "$container_name" -- sudo dnf install -y \
        python3-gobject gtk4 libadwaita openfortivpn
    
    # Export app from container
    echo -e "${BLUE}Exportando aplicação do container...${NC}"
    
    # Create wrapper script that runs inside distrobox
    mkdir -p "$BIN_DIR"
    cat > "$BIN_LINK" << EOF
#!/bin/bash
distrobox enter $container_name -- python3 -m openfortivpn_gtk "\$@"
EOF
    chmod +x "$BIN_LINK"
    
    # Copy app files to a location accessible by distrobox
    mkdir -p "$INSTALL_DIR"
    cp -r "$SCRIPT_DIR/openfortivpn_gtk" "$INSTALL_DIR/"
    
    # Update wrapper to use local files
    cat > "$BIN_LINK" << EOF
#!/bin/bash
cd "$INSTALL_DIR"
distrobox enter $container_name -- python3 -m openfortivpn_gtk "\$@"
EOF
    chmod +x "$BIN_LINK"
    
    echo -e "${GREEN}✓ Container configurado${NC}"
    DISTROBOX_MODE=true
}

# Create user directories
create_directories() {
    echo -e "\n${BLUE}Criando diretórios...${NC}"
    
    mkdir -p "$INSTALL_DIR"
    mkdir -p "$BIN_DIR"
    mkdir -p "$DESKTOP_DIR"
    mkdir -p "$DESKTOP_DIR"
    mkdir -p "$ICON_DIR"
    mkdir -p "$ICON_PNG_DIR"
    
    # Ensure ~/.local/bin is in PATH
    if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
        echo -e "${YELLOW}⚠ $HOME/.local/bin não está no PATH${NC}"
        echo -e "${YELLOW}  Adicione ao seu ~/.bashrc ou ~/.zshrc:${NC}"
        echo -e "${CYAN}  export PATH=\"\$HOME/.local/bin:\$PATH\"${NC}"
    fi
    
    echo -e "${GREEN}✓ Diretórios criados${NC}"
}

# Install application files
install_app() {
    echo -e "\n${BLUE}Instalando aplicação...${NC}"
    
    # Copy application files
    cp -r "$SCRIPT_DIR/openfortivpn_gtk" "$INSTALL_DIR/"
    
    cp "$SCRIPT_DIR/data/openfortivpn-gtk.svg" "$ICON_DIR/openfortivpn-gtk.svg"
    cp "$SCRIPT_DIR/data/openfortivpn-gtk.png" "$ICON_PNG_DIR/openfortivpn-gtk.png"
    
    # Create launcher script (unless using distrobox)
    if [ "$DISTROBOX_MODE" != "true" ]; then
        cat > "$BIN_LINK" << EOF
#!/bin/bash
cd "$INSTALL_DIR"
exec /usr/bin/python3 -m openfortivpn_gtk "\$@"
EOF
        chmod +x "$BIN_LINK"
    fi
    
    echo -e "${GREEN}✓ Aplicação instalada em $INSTALL_DIR${NC}"
}

# Create desktop entry
create_desktop_entry() {
    echo -e "\n${BLUE}Criando entrada no menu...${NC}"
    
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
    
    # Update desktop database
    if command -v update-desktop-database &> /dev/null; then
        update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
    fi
    
    echo -e "${GREEN}✓ Entrada de menu criada${NC}"
}

# Create uninstall script
create_uninstaller() {
    cat > "$INSTALL_DIR/uninstall.sh" << EOF
#!/bin/bash
echo "Removendo OpenFortiVPN GTK..."
rm -rf "$INSTALL_DIR"
rm -f "$BIN_LINK"
rm -f "$DESKTOP_FILE"
rm -f "$ICON_DIR/openfortivpn-gtk.svg" "$ICON_PNG_DIR/openfortivpn-gtk.png"
echo "✓ Removido com sucesso"
EOF
    chmod +x "$INSTALL_DIR/uninstall.sh"
}

# Print completion message
print_success() {
    echo -e "\n${GREEN}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║               Instalação concluída com sucesso!              ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    echo -e "A aplicação foi instalada em:"
    echo -e "  ${CYAN}$INSTALL_DIR${NC}"
    echo -e ""
    echo -e "Você pode executar de duas formas:"
    echo -e ""
    echo -e "  ${BLUE}1. Pelo terminal:${NC}"
    echo -e "     openfortivpn-gtk"
    echo -e ""
    echo -e "  ${BLUE}2. Pelo menu de aplicações:${NC}"
    echo -e "     Procure por 'OpenFortiVPN'"
    echo -e ""
    
    if [ "$DISTROBOX_MODE" = "true" ]; then
        echo -e "${YELLOW}Nota: A aplicação roda dentro de um container Distrobox${NC}"
        echo -e "${YELLOW}      para acesso às bibliotecas necessárias.${NC}"
        echo -e ""
    fi
    
    echo -e "Para desinstalar:"
    echo -e "  ${CYAN}$INSTALL_DIR/uninstall.sh${NC}"
    echo -e ""
    
    # Check PATH
    if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
        echo -e "${YELLOW}╔══════════════════════════════════════════════════════════════╗"
        echo -e "║  IMPORTANTE: Adicione ~/.local/bin ao seu PATH               ║"
        echo -e "║                                                              ║"
        echo -e "║  Execute:                                                    ║"
        echo -e "║  echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc  ║"
        echo -e "║  source ~/.bashrc                                            ║"
        echo -e "╚══════════════════════════════════════════════════════════════╝${NC}"
    fi
}

# Uninstall function
uninstall() {
    echo -e "${YELLOW}Desinstalando OpenFortiVPN GTK...${NC}"
    
    rm -rf "$INSTALL_DIR"
    rm -f "$BIN_LINK"
    rm -f "$DESKTOP_FILE"
    rm -f "$ICON_DIR/openfortivpn-gtk.svg" "$ICON_PNG_DIR/openfortivpn-gtk.png"
    
    # Remove distrobox container if it exists
    if command -v distrobox &> /dev/null; then
        distrobox rm openfortivpn-gtk --force 2>/dev/null || true
    fi
    
    echo -e "${GREEN}✓ OpenFortiVPN GTK foi removido${NC}"
}

# Main
main() {
    DISTROBOX_MODE=false
    
    # Check for uninstall flag
    if [[ "$1" == "--uninstall" ]] || [[ "$1" == "-u" ]]; then
        uninstall
        exit 0
    fi
    
    # Check for help flag
    if [[ "$1" == "--help" ]] || [[ "$1" == "-h" ]]; then
        echo "OpenFortiVPN GTK - Instalador para Sistemas Atômicos"
        echo ""
        echo "Uso: $0 [opções]"
        echo ""
        echo "Opções:"
        echo "  --help, -h        Mostra esta ajuda"
        echo "  --uninstall, -u   Remove a aplicação"
        echo "  --distrobox       Força uso do Distrobox"
        echo ""
        echo "Este instalador é projetado para sistemas com raiz imutável:"
        echo "  • Fedora Silverblue"
        echo "  • Fedora Kinoite"
        echo "  • Bazzite"
        echo "  • Universal Blue"
        echo "  • VanillaOS"
        echo ""
        exit 0
    fi
    
    detect_atomic
    
    # Force distrobox mode if requested
    if [[ "$1" == "--distrobox" ]]; then
        install_via_distrobox
    else
        check_requirements
    fi
    
    create_directories
    install_app
    create_desktop_entry
    create_uninstaller
    print_success
}

# Run main
main "$@"

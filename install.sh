#!/bin/bash

# Printserver Installation Script
# This script sets up the printserver on a new system

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration variables
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TAPO_EMAIL=""
TAPO_PASSWORD=""
INSTALL_SAMBA=true
CONFIGURE_PRINTERS=false
INSTALL_WEB_DASHBOARD=true

# Functions
print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}  Printserver Installation${NC}"
    echo -e "${BLUE}================================${NC}"
    echo
}

print_step() {
    echo -e "${GREEN}[STEP]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_root() {
    if [[ $EUID -eq 0 ]]; then
        print_error "This script should not be run as root. Please run as a regular user with sudo access."
        exit 1
    fi
}

get_credentials() {
    echo -e "${YELLOW}Tapo Smart Plug Configuration${NC}"
    echo "Please enter your Tapo account credentials:"
    read -p "Tapo Email: " TAPO_EMAIL
    read -s -p "Tapo Password: " TAPO_PASSWORD
    echo
    if [[ -z "$TAPO_EMAIL" || -z "$TAPO_PASSWORD" ]]; then
        print_error "Both email and password are required."
        exit 1
    fi
}

# Main installation function
install_system_packages() {
    print_step "Installing system packages..."

    # Update package lists
    sudo apt-get update

    # Install CUPS
    sudo apt-get install -y cups

    # Install Samba if requested
    if [[ "$INSTALL_SAMBA" == "true" ]]; then
        sudo apt-get install -y samba
    fi

    # Install Python and pip if not present
    sudo apt-get install -y python3 python3-pip python3-venv

    print_step "System packages installed successfully"
}

configure_cups() {
    print_step "Configuring CUPS..."

    # Backup original configuration
    sudo cp /etc/cups/cupsd.conf /etc/cups/cupsd.conf.backup

    # Configure CUPS for network access
    sudo tee -a /etc/cups/cupsd.conf > /dev/null << 'EOF'

# Printserver configuration
Listen *:631
Listen 0.0.0.0:631

Browsing On
BrowseOrder allow,deny
BrowseAllow all

<Location />
  Order allow,deny
  Allow all
</Location>

<Location /admin>
  Order allow,deny
  Allow all
</Location>

MaxJobTime 86400
MaxJobs 25
PreserveJobHistory Yes
PreserveJobFiles Yes
EOF

    # Restart CUPS
    sudo systemctl restart cups
    sudo systemctl enable cups

    print_step "CUPS configured successfully"
}

configure_samba() {
    if [[ "$INSTALL_SAMBA" == "true" ]]; then
        print_step "Configuring Samba for Windows printer sharing..."

        # Backup original configuration
        sudo cp /etc/samba/smb.conf /etc/samba/smb.conf.backup

        # Configure Samba
        sudo tee -a /etc/samba/smb.conf > /dev/null << 'EOF'

[printers]
   comment = All Printers
   path = /var/spool/samba
   browseable = yes
   guest ok = yes
   writable = no
   printable = yes
   public = yes
EOF

        # Create spool directory
        sudo mkdir -p /var/spool/samba
        sudo chmod 1777 /var/spool/samba

        # Restart Samba
        sudo systemctl restart smbd
        sudo systemctl enable smbd

        print_step "Samba configured successfully"
    fi
}

setup_python_environment() {
    print_step "Setting up Python virtual environment..."

    cd "$PROJECT_DIR"

    # Create virtual environment
    python3 -m venv venv

    # Activate virtual environment and install dependencies
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt

    print_step "Python environment set up successfully"
}

configure_environment() {
    print_step "Configuring environment variables..."

    # Add to user's bashrc
    if ! grep -q "TAPO_EMAIL" ~/.bashrc; then
        echo "export TAPO_EMAIL=\"$TAPO_EMAIL\"" >> ~/.bashrc
        echo "export TAPO_PASSWORD=\"$TAPO_PASSWORD\"" >> ~/.bashrc
    fi

    # Also set for current session
    export TAPO_EMAIL="$TAPO_EMAIL"
    export TAPO_PASSWORD="$TAPO_PASSWORD"

    print_step "Environment variables configured"
}

install_custom_backend() {
    print_step "Installing custom CUPS backend..."

    # Install the always-available backend
    sudo cp always-available-backend /usr/lib/cups/backend/always-available
    sudo chmod +x /usr/lib/cups/backend/always-available

    # Configure sudo permissions for CUPS lp user
    echo "lp ALL=(ALL) NOPASSWD:SETENV: /usr/lib/cups/backend/usb" | sudo tee /etc/sudoers.d/cups-usb
    echo "lp ALL=(ALL) NOPASSWD: /usr/bin/udevadm trigger --subsystem-match=usb" | sudo tee -a /etc/sudoers.d/cups-usb

    # Restart CUPS to load new backend
    sudo systemctl restart cups

    print_step "Custom CUPS backend installed"
}

setup_systemd_service() {
    print_step "Setting up systemd service..."

    # Copy service file
    sudo cp cups-tapo.service /etc/systemd/system/

    # Update service file with actual path
    sudo sed -i "s|WorkingDirectory=.*|WorkingDirectory=$PROJECT_DIR|" /etc/systemd/system/cups-tapo.service
    sudo sed -i "s|ExecStart=.*|ExecStart=$PROJECT_DIR/venv/bin/python $PROJECT_DIR/scripts/printserver_cups_tapo.py|" /etc/systemd/system/cups-tapo.service

    # Reload systemd and enable service
    sudo systemctl daemon-reload
    sudo systemctl enable cups-tapo

    print_step "Systemd service configured"
}

setup_web_dashboard_service() {
    if [[ "$INSTALL_WEB_DASHBOARD" == "true" ]]; then
        print_step "Setting up web dashboard systemd service..."

        # Copy service file
        sudo cp web-dashboard.service /etc/systemd/system/

        # Update service file with actual path
        sudo sed -i "s|WorkingDirectory=.*|WorkingDirectory=$PROJECT_DIR|" /etc/systemd/system/web-dashboard.service
        sudo sed -i "s|ExecStart=.*|ExecStart=$PROJECT_DIR/venv/bin/python $PROJECT_DIR/scripts/web_dashboard.py|" /etc/systemd/system/web-dashboard.service

        # Reload systemd and enable service
        sudo systemctl daemon-reload
        sudo systemctl enable web-dashboard

        print_step "Web dashboard systemd service configured"
    fi
}

configure_printers() {
    if [[ "$CONFIGURE_PRINTERS" == "true" ]]; then
        print_step "Printer configuration..."

        echo "Please configure your printers through the CUPS web interface:"
        echo "1. Open https://$(hostname -I | awk '{print $1}'):631 in your browser"
        echo "2. Go to Administration > Add Printer"
        echo "3. Select your printer and configure it"
        echo "4. Note the printer names for config.py"
        echo
        echo "After adding printers, update config.py with printer names and Tapo plug IPs"
        echo "Example config.py entry:"
        echo "PRINTERS = {"
        echo "    \"HP_LaserJet_CP1525N\": \"192.168.1.100\","
        echo "    \"Printer_Name\": \"Plug_IP\""
        echo "}"
    fi
}

test_installation() {
    print_step "Testing installation..."

    cd "$PROJECT_DIR"

    # Test Python environment
    source venv/bin/activate
    python -c "import asyncio; from kasa import Discover; print('Python dependencies OK')"

    # Test Tapo discovery
    echo "Testing Tapo device discovery..."
    python scripts/discover.py

    print_step "Installation test completed"
}

show_post_installation_steps() {
    echo
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}  Post-Installation Steps${NC}"
    echo -e "${BLUE}================================${NC}"
    echo
    echo "1. Configure printers in CUPS web interface:"
    echo "   https://$(hostname -I | awk '{print $1}'):631"
    echo
    echo "2. Update config.py with your printer names and Tapo plug IPs"
    echo
    echo "3. Test the services:"
    echo "   sudo systemctl start cups-tapo"
    echo "   sudo systemctl status cups-tapo"
    echo "   sudo systemctl start web-dashboard"
    echo "   sudo systemctl status web-dashboard"
    echo
    echo "4. Access the web dashboard:"
    echo "   http://$(hostname -I | awk '{print $1}'):5000"
    echo
    echo "5. View logs:"
    echo "   sudo journalctl -u cups-tapo -f"
    echo "   sudo journalctl -u web-dashboard -f"
    echo
    echo "6. For Windows sharing, ensure printers are shared in CUPS"
    echo
}

# Main execution
main() {
    print_header
    check_root

    echo "This script will install and configure the printserver on your system."
    echo "Make sure you have:"
    echo "- Tapo smart plugs set up and connected to your network"
    echo "- Printers connected (USB or network)"
    echo "- Static IPs assigned to Tapo plugs in your router"
    echo

    read -p "Do you want to install Samba for Windows printer sharing? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        INSTALL_SAMBA=false
    fi

    get_credentials

    read -p "Do you want to configure printers now? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        CONFIGURE_PRINTERS=true
    fi

    # Run installation steps
    install_system_packages
    configure_cups
    configure_samba
    setup_python_environment
    configure_environment
    install_custom_backend
    setup_systemd_service
    setup_web_dashboard_service
    configure_printers
    test_installation

    show_post_installation_steps

    echo -e "${GREEN}Installation completed successfully!${NC}"
}

# Run main function
main "$@"

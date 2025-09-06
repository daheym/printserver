# Printserver

A Python-based service that automatically manages power for network printers using CUPS print queues and Tapo smart plugs. The system monitors printer job queues and turns printers on when jobs are present, then powers them off after a configurable delay when no jobs remain.

## Prerequisites

### CUPS Configuration
CUPS (Common Unix Printing System) must be installed and configured for network printing.

1. Install CUPS:
   ```bash
   sudo apt-get install cups
   ```

2. Modify `/etc/cups/cupsd.conf` to enable network access:
   ```conf
   # Listen on all interfaces
   Listen *:631
   # Or for specific interface
   Listen 0.0.0.0:631

   # Enable browsing
   Browsing On
   BrowseOrder allow,deny
   BrowseAllow all

   # Allow remote administration (optional)
   <Location />
     Order allow,deny
     Allow all
   </Location>
   ```

3. Restart CUPS service:
   ```bash
   sudo systemctl restart cups
   ```

### Samba Configuration (for Windows Printer Sharing)
If sharing printers with Windows clients, configure Samba:

1. Install Samba:
   ```bash
   sudo apt-get install samba
   ```

2. Modify `/etc/samba/smb.conf`:
   ```conf
   [global]
   workgroup = WORKGROUP
   server string = Print Server
   security = user
   map to guest = Bad User

   [printers]
   comment = All Printers
   path = /var/spool/samba
   browseable = yes
   guest ok = yes
   writable = no
   printable = yes
   public = yes
   ```

3. Create spool directory and set permissions:
   ```bash
   sudo mkdir -p /var/spool/samba
   sudo chmod 1777 /var/spool/samba
   ```

4. Restart Samba:
   ```bash
   sudo systemctl restart smbd
   ```

### Always-Available CUPS Backend (for Windows Clients)
To make printers appear always available to Windows clients (even when powered off), use the custom CUPS backend:

1. Install the backend:
   ```bash
   sudo cp always-available-backend /usr/lib/cups/backend/always-available
   sudo chmod +x /usr/lib/cups/backend/always-available
   ```

2. Update printer configuration to use the new backend:
   ```bash
   sudo lpadmin -p HP_LaserJet_CP1525N -v always-available://HP/LaserJet%20CP1525N?serial=00CNCF134031
   ```

3. Restart CUPS:
   ```bash
   sudo systemctl restart cups
   ```

**Note**: This backend forwards all print jobs to the original USB backend, ensuring compatibility while making printers appear always available to Windows clients.

### Tapo Devices
- Tapo smart plugs must be installed and connected to the same network
- Note the IP addresses of the plugs connected to printers
- Create a Tapo account and note the email/password for API access

### Python Dependencies
- Python 3.7+
- Required packages: `kasa` (for Tapo control)

## Installation

1. Clone this repository:
   ```bash
   git clone <repository-url>
   cd printserver
   ```

2. Install dependencies:
   ```bash
   pip install python-kasa
   ```

3. Set environment variables for Tapo credentials. You can include these lines in your `~/.bashrc`:
   ```bash
   export TAPO_EMAIL="your-tapo-email@example.com"
   export TAPO_PASSWORD="your-tapo-password"
   ```

## Configuration

### Environment Variables
- `TAPO_EMAIL`: Your Tapo account email
- `TAPO_PASSWORD`: Your Tapo account password

### Printer Mapping
Edit `scripts/printserver_cups_tapo.py` and update the `PRINTERS` dictionary:
```python
PRINTERS = {
    "HP_LaserJet_CP1525N": "192.168.0.114",
    # Add more printers as needed
    # "Printer_Name": "Plug_IP"
}
```

### Timing Configuration
Adjust these values in `scripts/printserver_cups_tapo.py`:
- `CHECK_INTERVAL`: Seconds between CUPS queue checks (default: 10)
- `TURN_OFF_DELAY`: Seconds to wait after last job before powering off (default: 60)

## Usage

### Manual Execution
Run the automated print server:
```bash
python scripts/printserver_cups_tapo.py
```

### Systemd Service (Recommended)
For automatic startup and management:

1. Copy the service file:
   ```bash
   sudo cp cups-tapo.service /etc/systemd/system/
   ```

   **Note**: The service file is configured with `After=network-online.target cups.service` to ensure it starts only after:
   - The network is fully online and routable
   - The CUPS printing service is running
   This prevents connection errors during system boot.

2. Update the environment variables in the service file with your actual Tapo credentials:
   ```bash
   sudo nano /etc/systemd/system/cups-tapo.service
   ```

3. Reload systemd and enable the service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable cups-tapo
   ```

4. Start the service:
   ```bash
   sudo systemctl start cups-tapo
   ```

5. Check status:
   ```bash
   sudo systemctl status cups-tapo
   ```

6. View logs:
   ```bash
   sudo journalctl -u cups-tapo -f
   ```

7. **Optional: Configure log retention** (logs are kept for 24 hours by default):
   ```bash
   sudo nano /etc/systemd/journald.conf
   # Add: MaxRetentionSec=24h
   sudo systemctl restart systemd-journald
   ```

### Device Discovery
Find Tapo devices on your network:
```bash
python scripts/discover.py
```

### Manual Testing
Test individual plug control with user prompts:
```bash
python scripts/tapo_test.py
```

## Scripts Overview

- `always-available-backend`: Custom CUPS backend that makes printers appear always available to Windows clients
- `scripts/printserver_cups_tapo.py`: Main service that monitors CUPS queues and controls plugs
- `scripts/discover.py`: Discovers all Tapo devices on the network
- `scripts/tapo_test.py`: Manual control script for testing individual plugs

## Troubleshooting

### CUPS Issues
- Ensure CUPS is running: `sudo systemctl status cups`
- Check printer status: `lpstat -p`
- View print jobs: `lpstat -o`

### Tapo Connection Issues
- Verify device IPs using `scripts/discover.py`
- Check network connectivity to plugs
- Ensure Tapo credentials are correct

### Permission Issues
- Run scripts with appropriate permissions for CUPS access
- Ensure Samba has correct file permissions if using Windows sharing

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

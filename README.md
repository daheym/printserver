# Printserver

A Python-based service that automatically manages power for network printers using CUPS print queues and Tapo smart plugs. The system monitors printer job queues and turns printers on when jobs are present, then powers them off after a configurable delay when no jobs remain.

## Prerequisites

### CUPS Configuration
CUPS (Common Unix Printing System) must be installed and configured for network printing.

1. Update package lists and upgrade system:
   ```bash
   sudo apt-get update
   sudo apt-get upgrade
   ```

2. Install CUPS:
   ```bash
   sudo apt-get install cups
   ```

3. Modify `/etc/cups/cupsd.conf` to enable network access and configure job management:
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

   # Set how long / how many jobs are stored
   #MaxJobTime 86400
   MaxJobs 25
   PreserveJobHistory Yes
   PreserveJobFiles Yes
   ```

4. Restart CUPS service:
   ```bash
   sudo systemctl restart cups
   ```

5. Add printers through the CUPS web interface:
   - Open `https://[Raspi-IP]:631/` in your browser (accept the security warning for self-signed certificate)
   - Click the "Administration" tab
   - Click "Add Printer"
   - Select your printer from the list (for USB printers, choose the USB connection; for network printers, choose the appropriate network protocol)
   - Enter a name, description, and location for the printer
   - Select the printer make and model from the database, or provide a PPD file if you have one
   - Click "Add Printer" to complete the setup
   - Test the printer by printing a test page from the printer's maintenance page

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

2. Configure sudo permissions for the CUPS lp user:
   ```bash
   echo "lp ALL=(ALL) NOPASSWD:SETENV: /usr/lib/cups/backend/usb" | sudo tee /etc/sudoers.d/cups-usb
   ```

3. Update printer configuration to use the new backend:
   ```bash
   sudo lpadmin -p [PRINTER_NAME] -v always-available://[PRINTER_NAME]
   ```

   **Note**: Replace `[PRINTER_NAME]` with your actual printer name (as shown in CUPS). You can find the printer name using `lpstat -p`.

4. Restart CUPS:
   ```bash
   sudo systemctl restart cups
   ```

**Note**: This backend forwards all print jobs to the original USB backend, ensuring compatibility while making printers appear always available to Windows clients.

#### Backend Modifications and Security
The `always-available-backend` was modified to fix several issues:

- **Fixed stdin/stdout redirection**: The backend now properly forwards stdin, stdout, and stderr to the USB backend using `subprocess.run()` with appropriate parameters
- **Resolved permission issues**: CUPS backends run as the `lp` user, but USB devices require root access. The backend uses `sudo` to execute the USB backend with proper permissions
- **Environment variable preservation**: Uses `sudo -E` with `SETENV` in sudoers to preserve the `DEVICE_URI` environment variable

**Security Considerations**: Granting sudo permissions to the `lp` user is generally not recommended from a security perspective. However, in this specific case:
- The permission is restricted to only the `/usr/lib/cups/backend/usb` command
- The `lp` user already has limited privileges and is specifically designed for print operations
- USB backend access is necessary for printer communication
- The permission is equivalent to what CUPS would have if it ran backends as root

If security is a major concern, consider running CUPS backends as root or implementing a more restricted USB access mechanism.

### Tapo Devices
- Tapo smart plugs must be installed and connected to the same network
- I used Tapo P110 smart plugs, but other models might work as well
- Plug your printer into the plug
- Note the IP addresse of the plug connected to printer
- Create a Tapo account and note the email/password for API access
- In your router settings, set a stable IP for your plug

### Python Dependencies
- Python 3.7+
- Required packages: `python-kasa` (for Tapo control)

## Installation

1. On your Raspi, clone this repository:
   ```bash
   git clone https://github.com/daheym/printserver
   cd printserver
   ```

2. Install dependencies into a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate
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

### Centralized Configuration (config.py)
The system uses a centralized configuration file `config.py` to manage printer mappings and credentials. This file is shared across all scripts for consistency.

#### Configuration Structure
```python
# config.py
import os

# Map CUPS printer name -> Tapo plug IP
PRINTERS = {
    "HP_LaserJet_CP1525N": "192.168.0.114",
    "HP_Laserjet_2100TN": "192.168.0.116",
    # Add more printers as needed
    # "Printer_Name": "Plug_IP"
}

# Credentials from environment variables
TAPO_EMAIL = os.environ.get('TAPO_EMAIL', 'default@example.com')
TAPO_PASSWORD = os.environ.get('TAPO_PASSWORD', 'default_password')
```

#### How to Configure
1. Edit `config.py` in the root directory:
   ```bash
   nano config.py
   ```

2. Update the `PRINTERS` dictionary with your printer names and corresponding Tapo plug IPs:
   - **Printer Name**: Must match the CUPS printer name exactly (use `lpstat -p` to verify)
   - **IP Address**: The static IP of the Tapo smart plug connected to that printer

3. Ensure your Tapo credentials are set in environment variables (see Installation section)

#### Benefits
- **Centralized Management**: All printer configurations in one place
- **Consistency**: All scripts use the same configuration
- **Easy Maintenance**: Add/remove printers by editing one file
- **Scalability**: Simple to expand with additional printers

**Note**: The `config.py` file is automatically imported by all scripts. No additional configuration steps are needed after editing this file.

### Timing Configuration
Adjust these values in `scripts/printserver_cups_tapo.py`:
- `CHECK_INTERVAL`: Seconds between CUPS queue checks (default: 30)
- `TURN_OFF_DELAY`: Seconds to wait after last job before powering off (default: 600)

### Energy Monitoring
The system includes built-in energy consumption tracking for Tapo plugs that support energy monitoring:

- **Automatic Logging**: Energy data is logged when printers are powered off
- **Real-time Power**: Current power consumption in watts
- **Daily/Monthly Totals**: Accumulated energy usage in kWh
- **Supported Devices**: Works with Tapo plugs that have energy monitoring capabilities

Energy information appears in logs like:
```
[14:30:15] HP_LaserJet_CP1525N: Turning OFF plug 192.168.0.114 | Energy: 0.45 W | Total: 2.134 kWh
```

Test energy monitoring with:
```bash
python scripts/test_energy.py
```

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
   ```
   sudo journalctl -u cups-tapo -f
   ```

   To view all logs at once (without pager):
   ```
   sudo journalctl -u cups-tapo --no-pager
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

For automated testing without prompts:
```bash
python scripts/test_iotplug.py
```

## Scripts Overview

- `always-available-backend`: Custom CUPS backend that makes printers appear always available to Windows clients
- `scripts/printserver_cups_tapo.py`: Main service that monitors CUPS queues and controls plugs
- `scripts/discover.py`: Discovers all Tapo devices on the network
- `scripts/tapo_test.py`: Manual control script for testing individual plugs with user prompts
- `scripts/test_energy.py`: Tests energy monitoring capabilities of Tapo plugs
- `scripts/test_iotplug.py`: Simple script to toggle plug state without prompts

## Troubleshooting

### CUPS Issues
- Ensure CUPS is running: `sudo systemctl status cups`
- Check printer status: `lpstat -p`
- View print jobs: `lpstat -o`

### Tapo Connection Issues
- Verify device IPs using `scripts/discover.py`
- Check network connectivity to plugs
- Ensure Tapo credentials are correct

### Logging Delays
If you notice that log timestamps in `journalctl` are significantly behind real time (e.g., script timestamps show [12:06:32] but journalctl shows Sep 08 15:18:45), this is due to Python's output buffering when running as a systemd service.

**Solution**: Add the following line to your `/etc/systemd/system/cups-tapo.service` file in the `[Service]` section:
```ini
Environment=PYTHONUNBUFFERED=1
```

Then reload and restart the service:
```bash
sudo systemctl daemon-reload
sudo systemctl restart cups-tapo
```

This disables Python's stdout/stderr buffering, ensuring logs appear in real-time.

### Permission Issues
- Run scripts with appropriate permissions for CUPS access
- Ensure Samba has correct file permissions if using Windows sharing

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

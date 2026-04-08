# Printserver

A Python-based service that automatically manages power for network printers using CUPS print queues and Tapo smart plugs. The system monitors printer job queues and turns printers on when jobs are present, then powers them off after a configurable delay when no jobs remain.

## How It Works

1. **Print Job Detection**: Monitors CUPS print queues for new jobs
2. **Smart Power Management**: Automatically powers on printers when jobs are queued
3. **Energy Saving**: Powers off printers after a configurable delay when queues are empty
4. **USB Device Handling**: Includes intelligent USB device detection and port scanning for reliable printing
5. **Windows Compatibility**: Custom CUPS backend makes printers appear always available to Windows clients
6. **Energy Monitoring**: Tracks power consumption for supported Tapo plugs

## Quick Start

```bash
git clone https://github.com/daheym/printserver
cd printserver
./install.sh
```

That's it! The automated script handles everything. Then configure your printers and plugs in `config.py`. Runtime settings changed from the web dashboard are stored separately in `runtime_config.json`.

## Supported Hardware

### Tested Printers
- HP LaserJet CP1525N
- HP LaserJet 2100TN
- Most USB and network printers (via CUPS)

### Tapo Smart Plugs
- Tapo P110 (recommended, includes energy monitoring)
- Other Tapo smart plugs with power switching capability

### Operating Systems
- Ubuntu 18.04+
- Debian 10+
- Raspberry Pi OS
- Other Debian-based Linux distributions

## Prerequisites

### Quick Setup Requirements
- **Hardware**: Printers (USB/network) + Tapo smart plugs (one per printer)
- **Software**: Linux (Ubuntu/Debian), Python 3.7+, Tapo account with static IPs
- **Network**: All devices on same network with static IP assignments

**For automated installation**: Just run `./install.sh` - it handles everything below automatically.

### Detailed Manual Setup (Reference)
If you need to set up manually or understand what the automated script does, see below:

#### CUPS Configuration
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
To make printers appear always available to Windows clients (even when powered off), use the custom CUPS backend with automatic USB device detection:

1. Install the backend:
   ```bash
   sudo cp always-available-backend /usr/lib/cups/backend/always-available
   sudo chmod +x /usr/lib/cups/backend/always-available
   ```

2. Configure sudo permissions for the CUPS lp user (includes USB rescan permissions):
   ```bash
   echo "lp ALL=(ALL) NOPASSWD:SETENV: /usr/lib/cups/backend/usb" | sudo tee /etc/sudoers.d/cups-usb
   echo "lp ALL=(ALL) NOPASSWD: /usr/bin/udevadm trigger --subsystem-match=usb" | sudo tee -a /etc/sudoers.d/cups-usb
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

#### USB Device Detection and Auto-Rescan
The `always-available-backend` now includes automatic USB device detection and port scanning:

- **Automatic Device Detection**: Before processing print jobs, the backend checks if the USB printer is available
- **Port Rescan on Failure**: If the device isn't found, it automatically triggers a USB subsystem rescan using `udevadm trigger`
- **Retry Logic**: Configurable retry attempts (default: 3) with delays between attempts
- **Logging**: Detailed syslog logging for troubleshooting device detection issues

**Configuration Options** (in `always-available-backend`):
```python
USB_RESCAN_RETRIES = 3          # Number of rescan attempts
USB_RESCAN_DELAY = 2            # Seconds to wait after rescan
USB_DEVICE_CHECK_TIMEOUT = 5    # Timeout for device availability checks
```

#### Backend Modifications and Security
The `always-available-backend` includes several enhancements:

- **Fixed stdin/stdout redirection**: The backend now properly forwards stdin, stdout, and stderr to the USB backend using `subprocess.run()` with appropriate parameters
- **Resolved permission issues**: CUPS backends run as the `lp` user, but USB devices require root access. The backend uses `sudo` to execute the USB backend with proper permissions
- **Environment variable preservation**: Uses `sudo -E` with `SETENV` in sudoers to preserve the `DEVICE_URI` environment variable
- **USB device auto-detection**: Automatically detects and rescans USB ports when devices aren't immediately available
- **Enhanced logging**: Comprehensive syslog logging for troubleshooting

**Security Considerations**: Granting sudo permissions to the `lp` user is generally not recommended from a security perspective. However, in this specific case:
- The permissions are restricted to only the necessary commands: `/usr/lib/cups/backend/usb` and `/usr/bin/udevadm trigger --subsystem=usb`
- The `lp` user already has limited privileges and is specifically designed for print operations
- USB backend access and device rescan are necessary for printer communication
- The permissions are equivalent to what CUPS would have if it ran backends as root

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

### Automated Installation (Recommended)

1. Clone the repository:
   ```bash
   git clone https://github.com/daheym/printserver
   cd printserver
   ```

2. Run the automated installation script:
   ```bash
   ./install.sh
   ```

   The script will:
   - Install and configure CUPS
   - Set up Samba (optional)
   - Install the custom CUPS backend with USB scanning
   - Create a Python virtual environment
   - Install dependencies
   - Configure environment variables
   - Set up the systemd service

### Manual Installation (Advanced Users)

If you prefer manual installation, follow these steps:

1. Install system dependencies:
   ```bash
   sudo apt-get update
   sudo apt-get install cups samba python3 python3-pip python3-venv
   ```

2. Set up Python environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. Configure environment variables:
   ```bash
   export TAPO_EMAIL="your-tapo-email@example.com"
   export TAPO_PASSWORD="your-tapo-password"
   ```

## Configuration

### Tapo Credentials File
The system uses a credentials file `.tapo_credentials` in your home directory to securely store your Tapo account information.

**File Location**: `/home/pi/.tapo_credentials` (in your home directory)

**File Format**:
```bash
export TAPO_EMAIL="your-email@example.com"
export TAPO_PASSWORD="your-password"
```

**Security Notes**:
- The file contains your Tapo account credentials
- File permissions are set to `600` (owner read/write only)
- Keep this file secure and don't commit it to version control
- The automated installation script creates this file for you

**Manual Creation** (if needed):
```bash
# Create the credentials file
nano ~/.tapo_credentials

# Add your credentials (replace with actual values)
export TAPO_EMAIL="your-email@example.com"
export TAPO_PASSWORD="your-complex-password"

# Set proper permissions
chmod 600 ~/.tapo_credentials
```

### Environment Variables (Alternative)
As a fallback, you can also set credentials via environment variables:
- `TAPO_EMAIL`: Your Tapo account email
- `TAPO_PASSWORD`: Your Tapo account password

However, the credentials file approach is preferred for security and reliability.

### Centralized Configuration (`config.py`)
The system uses `config.py` for static configuration such as printer mappings, credentials, and the default shutdown delay. This file is shared across all scripts for consistency.

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
4. Set `TURN_OFF_DELAY` in `config.py` if you want a different default value for fresh installs or after deleting runtime overrides

#### Benefits
- **Centralized Management**: All printer configurations in one place
- **Consistency**: All scripts use the same configuration
- **Easy Maintenance**: Add/remove printers by editing one file
- **Scalability**: Simple to expand with additional printers

**Note**: The web dashboard no longer rewrites `config.py`. Live dashboard changes are stored in `runtime_config.json`, and `config.py` remains the source of defaults.

### Timing Configuration
Adjust these values in `scripts/printserver_cups_tapo.py`:
- `CHECK_INTERVAL`: Seconds between CUPS queue checks (default: 30)

Adjust this value in `config.py`:
- `TURN_OFF_DELAY`: Default seconds to wait after the last job before powering off (default: 600)

When the web dashboard changes the delay, the active value is written to `runtime_config.json` and picked up automatically by the running services. A service restart is only needed after code updates, not for normal delay changes.

The temporary auto-off disable window is also runtime-configurable through `runtime_config.json`:
- `auto_off_disable_duration`: How many seconds the "Disable Auto-Off" action should last (default: `7200`)
- `auto_off_disabled_until`: Absolute Unix timestamp until which auto-off remains disabled
- `auto_off_disable_users`: Lowercase CUPS usernames that should automatically trigger the same temporary disable window

Example `runtime_config.json` content:
```json
{
  "auto_off_disable_duration": 7200,
  "auto_off_disabled_until": 0,
  "auto_off_disable_users": ["alice", "bob"],
  "turn_off_delay": 600
}
```

`runtime_config.json` is intended as a local runtime-state file and is a good candidate for `.gitignore`, since the dashboard updates it frequently during normal use. Please create this file in your project folder, otherwise the defaults from `config.py` will be used as fallback. 

If you prefer to keep the default user allowlist in code, you can also edit `AUTO_OFF_DISABLE_USERS` in `config.py`. The runtime file overrides that default once present.

The internal deduplication history for automatically triggered jobs is stored separately in `auto_off_triggered_jobs.json`, which is also ignored by git.

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

### Web Dashboard
The web dashboard provides a user-friendly interface to monitor and control your print server.

Dashboard-managed runtime settings are stored in `runtime_config.json`. The file is created automatically the first time you change the turn-off delay or temporarily disable auto-off from the dashboard.

#### Manual Execution
```bash
python scripts/web_dashboard.py
```

Then open `http://localhost:5000` in your browser.

#### Automatic Service (Recommended)
For the web dashboard to run automatically on boot:

```bash
# Copy the service file
sudo cp web-dashboard.service /etc/systemd/system/

# Enable and start the service (credentials are inherited from environment)
sudo systemctl daemon-reload
sudo systemctl enable web-dashboard
sudo systemctl start web-dashboard

# Check status
sudo systemctl status web-dashboard
```

The dashboard will then be available at `http://localhost:5000` and start automatically on boot.

**Features:**
- **Monitor Print Jobs**: Real-time status of all configured printers
- **View Pending Jobs**: Detailed list of all queued print jobs with user and file information
- **Manual Plug Control**: Turn printers on/off manually
- **Countdown Timer**: Adjust the auto-shutoff delay (1-60 minutes)
- **Temporary Override**: Disable auto-shutoff for the configured runtime window (default: 2 hours, automatically reverts)
- **User-Based Override**: Automatically disable auto-off when configured CUPS users submit jobs

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

2. The service will inherit your Tapo credentials from the environment variables set during installation.

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

## Files Overview

### Core Files
- `install.sh`: **NEW** - Automated installation script that sets up the entire system
- `requirements.txt`: **NEW** - Python dependencies specification
- `always-available-backend`: Custom CUPS backend that makes printers appear always available to Windows clients
- `cups-tapo.service`: Systemd service configuration for automatic startup
- `config.py`: Static configuration for printer mappings, credentials, and default delay
- `runtime_config.py`: Shared helper for reading and writing dashboard-managed runtime settings
- `runtime_config.json`: Auto-generated runtime state file for live dashboard overrides
- `auto_off_triggered_jobs.json`: Auto-generated local history used to avoid retriggering the same job repeatedly

### Scripts
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

## FAQ

### Can I use this with network printers (not USB)?
Yes! The system works with any printer supported by CUPS, including network printers. Just add them through the CUPS web interface and configure the printer-to-plug mapping in `config.py`.

### What if my printer changes USB ports?
The custom CUPS backend includes intelligent USB device detection that automatically finds printers even when they connect to different USB ports after power cycles.

### Can I monitor energy usage?
Yes, if you use Tapo P110 plugs (or other energy-monitoring models), the system automatically logs power consumption data when printers are turned off.

### How do I add more printers?
1. Add the printer in CUPS web interface
2. Plug the printer into a Tapo smart plug
3. Set a static IP for the plug in your router
4. Add the mapping to `config.py`: `"Printer_Name": "192.168.1.100"`

### Do I need to restart services after changing the turn-off delay?
No for normal dashboard changes. The dashboard writes the active delay to `runtime_config.json`, and the main print service rereads it while running. You only need a restart after changing the application code or service configuration itself.

### Is this secure?
The system uses restricted sudo permissions only for necessary USB operations. The CUPS `lp` user gets minimal permissions required for printer communication. For high-security environments, consider running CUPS backends as root.

### What if the installation script fails?
You can still use the manual installation instructions provided in the "Detailed Manual Setup" section. The script is just a convenience wrapper around those steps.

### Can I run this on a Raspberry Pi?
Yes! This was designed for Raspberry Pi systems. Use Raspberry Pi OS (Debian-based) and follow the automated installation.

### How do I backup my configuration?
Backup `config.py`, `runtime_config.json` if it exists, and your environment variables. The installation script handles the rest.

## Recent Changes

- ✅ **Automated Installation**: New `install.sh` script for one-command setup
- ✅ **USB Device Detection**: Enhanced backend with automatic port scanning and device discovery
- ✅ **Python Dependencies**: Centralized `requirements.txt` for easy dependency management
- ✅ **Documentation**: Improved README with quick start guide and hardware compatibility

## Contributing

Contributions are welcome! Please:

1. Test your changes thoroughly
2. Update documentation as needed
3. Follow the existing code style
4. Add tests for new features

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

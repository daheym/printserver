#!/usr/bin/env python3
import asyncio
import datetime
import json
import os
import subprocess
import sys
import time
from flask import Flask, jsonify, request, render_template_string
from kasa import Discover

# Add parent directory to path for config import
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import PRINTERS, TAPO_EMAIL, TAPO_PASSWORD

def read_config_value(key):
    """Read a value from config.py file"""
    try:
        with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.py'), 'r') as f:
            content = f.read()
            # Simple parsing - look for the key = value line
            for line in content.split('\n'):
                line = line.strip()
                if line.startswith(key + ' = '):
                    value_str = line.split(' = ')[1]
                    # Remove comments
                    if '#' in value_str:
                        value_str = value_str.split('#')[0].strip()
                    # Try to evaluate as Python literal
                    try:
                        return eval(value_str)
                    except:
                        return value_str.strip()
        return None
    except Exception as e:
        print(f"Error reading {key} from config: {e}")
        return None

def write_config_value(key, value):
    """Write a value to config.py file"""
    try:
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.py')
        with open(config_path, 'r') as f:
            content = f.read()

        lines = content.split('\n')
        found = False
        for i, line in enumerate(lines):
            line_strip = line.strip()
            if line_strip.startswith(key + ' = '):
                # Replace the line
                lines[i] = f"{key} = {repr(value)}"
                found = True
                break

        if not found:
            # Add at the end
            lines.append(f"{key} = {repr(value)}")

        with open(config_path, 'w') as f:
            f.write('\n'.join(lines))

        return True
    except Exception as e:
        print(f"Error writing {key} to config: {e}")
        return False

app = Flask(__name__)

# Global state (in a real app, use a database or proper state management)
global_state = {
    'turn_off_delay': 600,  # Default 10 minutes
    'original_turn_off_delay': 600,  # Store original value
    'auto_off_disabled_until': 0,  # Timestamp when auto-off should be re-enabled
    'plug_status': {},
    'last_job_time': {},
    'last_update': 0
}



# HTML template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Print Server Dashboard</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
        }
        .printer-card {
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin: 10px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .printer-info {
            flex: 1;
        }
        .printer-name {
            font-size: 1.2em;
            font-weight: bold;
            margin-bottom: 5px;
        }
        .printer-status {
            color: #666;
        }
        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 5px;
        }
        .status-on { background-color: #4CAF50; }
        .status-off { background-color: #f44336; }
        .status-jobs { background-color: #2196F3; }
        .controls {
            display: flex;
            gap: 10px;
            align-items: center;
        }
        button {
            padding: 8px 16px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
        }
        .btn-on { background-color: #4CAF50; color: white; }
        .btn-off { background-color: #f44336; color: white; }
        .btn-update { background-color: #2196F3; color: white; }
        button:disabled {
            background-color: #cccccc;
            cursor: not-allowed;
        }
        .config-section {
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .config-item {
            margin: 10px 0;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .config-item label {
            min-width: 150px;
        }
        .config-item input {
            padding: 5px;
            border: 1px solid #ddd;
            border-radius: 4px;
            width: 100px;
        }
        .config-item input:disabled {
            background-color: #f5f5f5;
            color: #999;
        }
        .auto-off-section {
            margin-top: 20px;
            padding-top: 20px;
            border-top: 1px solid #eee;
        }
        .auto-off-status {
            margin: 10px 0;
            padding: 10px;
            border-radius: 4px;
            font-weight: bold;
        }
        .auto-off-disabled {
            background-color: #fff3cd;
            color: #856404;
            border: 1px solid #ffeaa7;
        }
        .auto-off-enabled {
            background-color: #d1ecf1;
            color: #0c5460;
            border: 1px solid #bee5eb;
        }
        .countdown {
            font-weight: bold;
            color: #ff9800;
        }
        .refresh-btn {
            background-color: #9c27b0;
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
            margin: 20px 0;
        }
        .last-update {
            text-align: center;
            color: #666;
            font-size: 14px;
            margin-top: 10px;
        }
        .jobs-section {
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .jobs-section h2 {
            margin-top: 0;
            color: #333;
        }
        .no-jobs {
            text-align: center;
            color: #666;
            font-style: italic;
            padding: 20px;
        }
        .job-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px;
            border-bottom: 1px solid #eee;
        }
        .job-item:last-child {
            border-bottom: none;
        }
        .job-info {
            flex: 1;
        }
        .job-printer {
            font-weight: bold;
            color: #2196F3;
        }
        .job-details {
            color: #666;
            font-size: 14px;
        }
        .job-user {
            font-weight: bold;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Print Server Dashboard</h1>
        <p>Monitor print jobs and control smart plugs</p>
    </div>

    <button class="refresh-btn" onclick="refreshData()">Refresh Data</button>

    <div id="printers-container">
        <!-- Printer cards will be inserted here -->
    </div>

    <div class="jobs-section">
        <h2>Pending Print Jobs</h2>
        <div id="jobs-container">
            <!-- Job items will be inserted here -->
        </div>
    </div>

    <div class="config-section">
        <h2>Configuration</h2>
        <div class="config-item">
            <label for="turnOffDelay">Turn Off Delay (seconds):</label>
            <input type="number" id="turnOffDelay" min="60" max="3600" step="60">
            <button onclick="updateConfig()">Update</button>
        </div>

        <div class="auto-off-section">
            <h3>Temporary Auto-Off Control</h3>
            <div id="auto-off-status" class="auto-off-status">
                <!-- Auto-off status will be shown here -->
            </div>
            <button id="disable-auto-off-btn" onclick="toggleAutoOff()" class="btn-update">Disable Auto-Off (2 hours)</button>
        </div>
    </div>

    <div class="last-update" id="last-update">
        <!-- Last update time will be shown here -->
    </div>

    <script>
        let currentData = {};
        let currentJobs = [];

        async function fetchData() {
            try {
                const [statusResponse, jobsResponse] = await Promise.all([
                    fetch('/api/status'),
                    fetch('/api/jobs')
                ]);

                currentData = await statusResponse.json();
                const jobsData = await jobsResponse.json();
                currentJobs = jobsData.jobs;

                updateUI();
            } catch (error) {
                console.error('Error fetching data:', error);
            }
        }

        function updateUI() {
            const container = document.getElementById('printers-container');
            const jobsContainer = document.getElementById('jobs-container');
            const lastUpdate = document.getElementById('last-update');
            const autoOffStatus = document.getElementById('auto-off-status');
            const disableBtn = document.getElementById('disable-auto-off-btn');

            // Update last update time
            const now = new Date();
            lastUpdate.textContent = `Last updated: ${now.toLocaleTimeString()}`;

            // Update config input field
            const turnOffDelayInput = document.getElementById('turnOffDelay');
            const updateButton = document.querySelector('button[onclick="updateConfig()"]');

            // Update auto-off status
            const isDisabled = currentData.config.auto_off_disabled;
            if (isDisabled) {
                autoOffStatus.className = 'auto-off-status auto-off-disabled';
                autoOffStatus.textContent = 'Auto-off is temporarily disabled (2 hours)';
                disableBtn.textContent = 'Re-enable Auto-Off';
                // Disable input and update button when auto-off is disabled
                turnOffDelayInput.disabled = true;
                updateButton.disabled = true;
            } else {
                autoOffStatus.className = 'auto-off-status auto-off-enabled';
                autoOffStatus.textContent = 'Auto-off is enabled';
                disableBtn.textContent = 'Disable Auto-Off (2 hours)';
                // Enable input and update button when auto-off is enabled
                turnOffDelayInput.disabled = false;
                updateButton.disabled = false;
            }

            // Show the actual current TURN_OFF_DELAY value (not always 600)
            // But when disabled, we still show the stored value for reference
            turnOffDelayInput.value = currentData.config.actual_turn_off_delay || 600;

            // Clear existing cards
            container.innerHTML = '';

            // Create printer cards
            for (const [printer, data] of Object.entries(currentData.printers)) {
                const card = document.createElement('div');
                card.className = 'printer-card';

                const hasJobs = data.has_jobs;
                const isOn = data.plug_status;
                const countdown = data.countdown_remaining;

                let statusText = '';
                let countdownInfo = '';

                if (isOn) {
                    if (hasJobs) {
                        statusText = '<span class="status-indicator status-jobs"></span>Active (jobs present)';
                        countdownInfo = '<div class="countdown">Will shut down after jobs complete</div>';
                    } else if (countdown > 0) {
                        statusText = '<span class="status-indicator status-on"></span>On';
                        const minutes = Math.floor(countdown / 60);
                        const seconds = Math.floor(countdown % 60);
                        countdownInfo = `<div class="countdown">Shuts down in ${minutes}:${seconds.toString().padStart(2, '0')}</div>`;
                    } else {
                        statusText = '<span class="status-indicator status-on"></span>On';
                        countdownInfo = '<div class="countdown">Shutting down soon</div>';
                    }
                } else {
                    statusText = '<span class="status-indicator status-off"></span>Off';
                }

                card.innerHTML = `
                    <div class="printer-info">
                        <div class="printer-name">${printer}</div>
                        <div class="printer-status">${statusText}</div>
                        ${countdownInfo}
                    </div>
                    <div class="controls">
                        <button class="btn-on" onclick="controlPlug('${printer}', 'on')" ${isOn ? 'disabled' : ''}>Turn On</button>
                        <button class="btn-off" onclick="controlPlug('${printer}', 'off')" ${!isOn ? 'disabled' : ''}>Turn Off</button>
                    </div>
                `;

                container.appendChild(card);
            }

            // Update jobs display
            jobsContainer.innerHTML = '';

            if (currentJobs.length === 0) {
                jobsContainer.innerHTML = '<div class="no-jobs">No pending print jobs</div>';
            } else {
                currentJobs.forEach(job => {
                    const jobItem = document.createElement('div');
                    jobItem.className = 'job-item';

                    jobItem.innerHTML = `
                        <div class="job-info">
                            <div class="job-printer">${job.printer}</div>
                            <div class="job-details">
                                Job #${job.job_id} by <span class="job-user">${job.user}</span> - ${job.file}
                            </div>
                        </div>
                    `;

                    jobsContainer.appendChild(jobItem);
                });
            }
        }

        async function controlPlug(printer, action) {
            try {
                const response = await fetch(`/api/plug/${printer}/${action}`, {
                    method: 'POST'
                });
                if (response.ok) {
                    await fetchData(); // Refresh data after action
                } else {
                    alert('Failed to control plug');
                }
            } catch (error) {
                console.error('Error controlling plug:', error);
                alert('Error controlling plug');
            }
        }

        async function updateConfig() {
            const delay = document.getElementById('turnOffDelay').value;
            try {
                const response = await fetch('/api/config', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ turn_off_delay: parseInt(delay) })
                });
                if (response.ok) {
                    await fetchData(); // Refresh data after config update
                } else {
                    alert('Failed to update configuration');
                }
            } catch (error) {
                console.error('Error updating config:', error);
                alert('Error updating configuration');
            }
        }

        async function toggleAutoOff() {
            const isDisabled = currentData.config.auto_off_disabled;
            try {
                const endpoint = isDisabled ? '/api/enable_auto_off' : '/api/disable_auto_off';
                const response = await fetch(endpoint, {
                    method: 'POST'
                });
                if (response.ok) {
                    location.reload(); // Reload the page immediately
                } else {
                    alert('Failed to toggle auto-off');
                }
            } catch (error) {
                console.error('Error toggling auto-off:', error);
                alert('Error toggling auto-off');
            }
        }

        async function refreshData() {
            await fetchData();
        }

        // Auto-refresh every 30 seconds
        setInterval(fetchData, 30000);

        // Initial load
        fetchData();
    </script>
</body>
</html>
"""

def cups_queue_has_jobs(printer_name):
    """Check if there are jobs in a CUPS printer queue"""
    result = subprocess.run(
        ["lpstat", "-o", printer_name], capture_output=True, text=True
    )
    return bool(result.stdout.strip())

def get_pending_jobs():
    """Get detailed information about all pending print jobs"""
    jobs = []
    try:
        # Get all jobs from all printers
        result = subprocess.run(
            ["lpstat", "-o"], capture_output=True, text=True
        )

        if result.stdout.strip():
            lines = result.stdout.strip().split('\n')
            for line in lines:
                # Parse lpstat output format: printer-jobid user date time file
                parts = line.split()
                if len(parts) >= 4:
                    printer_job = parts[0].split('-')
                    if len(printer_job) == 2:
                        printer_name = printer_job[0]
                        job_id = printer_job[1]
                        user = parts[1]
                        # Combine remaining parts for file name
                        file_info = ' '.join(parts[3:]) if len(parts) > 3 else 'Unknown'

                        jobs.append({
                            'printer': printer_name,
                            'job_id': job_id,
                            'user': user,
                            'file': file_info,
                            'status': 'pending'
                        })
    except Exception as e:
        print(f"Error getting pending jobs: {e}")

    return jobs

def get_printer_countdowns():
    """Get countdown information directly from journalctl logs"""
    countdowns = {}
    try:
        # Get recent logs from the cups-tapo service
        result = subprocess.run(
            ["sudo", "journalctl", "-u", "cups-tapo", "--no-pager", "-n", "100"],
            capture_output=True, text=True
        )

        if result.stdout.strip():
            lines = result.stdout.strip().split('\n')
            # Process lines in reverse order (most recent first)
            for line in reversed(lines):
                # Look for countdown messages: "[time] printer: No jobs, turning off in X seconds"
                if "No jobs, turning off in" in line and "seconds" in line:
                    # Parse the log format: "Dec 30 11:57:02 raspberrypi python3[282251]: [11:57:02] HP_Laserjet_2100TN: No jobs, turning off in 113 seconds"
                    # Find the second timestamp bracket
                    first_bracket_end = line.find(']')
                    if first_bracket_end > 0:
                        second_bracket_start = line.find('[', first_bracket_end)
                        if second_bracket_start > 0:
                            second_bracket_end = line.find(']', second_bracket_start)
                            if second_bracket_end > 0:
                                after_second_timestamp = line[second_bracket_end + 1:].strip()
                                # Now find the printer name before the first colon
                                colon_pos = after_second_timestamp.find(':')
                                if colon_pos > 0:
                                    printer_name = after_second_timestamp[:colon_pos].strip()

                                    # Find the countdown value
                                    countdown_part = "turning off in"
                                    countdown_start = line.find(countdown_part)
                                    if countdown_start > 0:
                                        after_countdown = line[countdown_start + len(countdown_part):]
                                        seconds_part = after_countdown.split()[0]
                                        try:
                                            countdown_seconds = int(seconds_part)
                                            # Only use this if we haven't seen this printer before (most recent)
                                            if printer_name not in countdowns:
                                                countdowns[printer_name] = countdown_seconds
                                        except ValueError:
                                            pass

    except Exception as e:
        print(f"Error getting countdowns from journalctl: {e}")

    return countdowns

async def get_plug_status(ip):
    """Get plug status asynchronously"""
    try:
        plug = await Discover.discover_single(ip, username=TAPO_EMAIL, password=TAPO_PASSWORD)
        await plug.update()
        status = plug.is_on
        if hasattr(plug, 'protocol') and hasattr(plug.protocol, 'close'):
            await plug.protocol.close()
        return status
    except Exception as e:
        print(f"Error getting plug status for {ip}: {e}")
        return False

async def control_plug(ip, action):
    """Control plug (on/off)"""
    try:
        plug = await Discover.discover_single(ip, username=TAPO_EMAIL, password=TAPO_PASSWORD)
        await plug.update()
        if action == 'on' and not plug.is_on:
            await plug.turn_on()
        elif action == 'off' and plug.is_on:
            await plug.turn_off()
        if hasattr(plug, 'protocol') and hasattr(plug.protocol, 'close'):
            await plug.protocol.close()
        return True
    except Exception as e:
        print(f"Error controlling plug {ip}: {e}")
        return False

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/status')
def get_status():
    """Get current status of all printers"""
    now = time.time()

    # Read current turn off delay from config
    current_turn_off_delay = read_config_value('TURN_OFF_DELAY') or 600

    # Determine if auto-off is disabled (TURN_OFF_DELAY = 7200 means disabled)
    auto_off_disabled = (current_turn_off_delay == 7200)

    # Get countdowns directly from journalctl logs
    journal_countdowns = get_printer_countdowns()

    printers_data = {}

    for printer, ip in PRINTERS.items():
        has_jobs = cups_queue_has_jobs(printer)
        plug_status = asyncio.run(get_plug_status(ip))

        # Use countdown from journalctl if available, otherwise calculate
        countdown_remaining = 0
        if plug_status:
            if has_jobs:
                # If printer has jobs, countdown starts after jobs are done
                countdown_remaining = -1  # Special value to indicate active with jobs
            elif printer in journal_countdowns:
                # Use countdown directly from journalctl
                countdown_remaining = journal_countdowns[printer]
            else:
                # Fallback: calculate using same logic as main service
                last_job = global_state['last_job_time'].get(printer, 0)
                if last_job > 0:
                    remaining = current_turn_off_delay - (now - last_job)
                    countdown_remaining = max(0, int(remaining))
                else:
                    # Just turned on, start countdown now
                    global_state['last_job_time'][printer] = now
                    countdown_remaining = current_turn_off_delay

        printers_data[printer] = {
            'has_jobs': has_jobs,
            'plug_status': plug_status,
            'countdown_remaining': countdown_remaining,
            'ip': ip
        }

    return jsonify({
        'printers': printers_data,
        'config': {
            'turn_off_delay': 600 if auto_off_disabled else current_turn_off_delay,  # Show 600 when disabled, actual value when enabled
            'actual_turn_off_delay': current_turn_off_delay,  # Always provide the actual value
            'auto_off_disabled': auto_off_disabled
        },
        'timestamp': now
    })

@app.route('/api/plug/<printer>/<action>', methods=['POST'])
def control_printer_plug(printer, action):
    """Control a specific printer's plug"""
    if printer not in PRINTERS:
        return jsonify({'error': 'Printer not found'}), 404

    if action not in ['on', 'off']:
        return jsonify({'error': 'Invalid action'}), 400

    ip = PRINTERS[printer]
    success = asyncio.run(control_plug(ip, action))

    if success:
        # Update global state
        global_state['plug_status'][printer] = (action == 'on')
        if action == 'on':
            global_state['last_job_time'][printer] = time.time()
        elif action == 'off':
            global_state['last_job_time'][printer] = 0

        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Failed to control plug'}), 500

@app.route('/api/config', methods=['GET', 'POST'])
def handle_config():
    """Get or update configuration"""
    if request.method == 'GET':
        current_delay = read_config_value('TURN_OFF_DELAY') or 600
        return jsonify({
            'turn_off_delay': current_delay,
            'auto_off_disabled': time.time() < global_state['auto_off_disabled_until']
        })
    elif request.method == 'POST':
        data = request.get_json()
        if 'turn_off_delay' in data:
            delay = int(data['turn_off_delay'])
            if 60 <= delay <= 3600:  # Between 1 minute and 1 hour
                if write_config_value('TURN_OFF_DELAY', delay):
                    return jsonify({'success': True})
                else:
                    return jsonify({'error': 'Failed to update config'}), 500
            else:
                return jsonify({'error': 'Invalid delay value'}), 400
        return jsonify({'error': 'Missing turn_off_delay'}), 400

@app.route('/api/disable_auto_off', methods=['POST'])
def disable_auto_off():
    """Temporarily disable auto-off for 2 hours by setting TURN_OFF_DELAY to 7200"""
    # Store original value
    global_state['original_turn_off_delay'] = read_config_value('TURN_OFF_DELAY') or 600

    # Set TURN_OFF_DELAY to 7200 (2 hours) to effectively disable auto-off
    if write_config_value('TURN_OFF_DELAY', 7200):
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Failed to disable auto-off'}), 500

@app.route('/api/enable_auto_off', methods=['POST'])
def enable_auto_off():
    """Re-enable auto-off by restoring TURN_OFF_DELAY to 600"""
    original_delay = global_state.get('original_turn_off_delay', 600)

    if write_config_value('TURN_OFF_DELAY', original_delay):
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Failed to enable auto-off'}), 500

@app.route('/api/jobs')
def get_jobs():
    """Get pending print jobs"""
    jobs = get_pending_jobs()
    return jsonify({'jobs': jobs})

if __name__ == '__main__':
    # Initialize global state
    for printer in PRINTERS:
        global_state['plug_status'][printer] = False
        global_state['last_job_time'][printer] = 0

    app.run(host='0.0.0.0', port=5000, debug=True)

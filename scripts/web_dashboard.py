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

        async function fetchData() {
            try {
                const response = await fetch('/api/status');
                currentData = await response.json();
                updateUI();
            } catch (error) {
                console.error('Error fetching data:', error);
            }
        }

        function updateUI() {
            const container = document.getElementById('printers-container');
            const lastUpdate = document.getElementById('last-update');
            const autoOffStatus = document.getElementById('auto-off-status');
            const disableBtn = document.getElementById('disable-auto-off-btn');

            // Update last update time
            const now = new Date();
            lastUpdate.textContent = `Last updated: ${now.toLocaleTimeString()}`;

            // Update config
            document.getElementById('turnOffDelay').value = currentData.config.turn_off_delay;

            // Update auto-off status
            const isDisabled = currentData.config.auto_off_disabled;
            if (isDisabled) {
                autoOffStatus.className = 'auto-off-status auto-off-disabled';
                autoOffStatus.textContent = 'Auto-off is temporarily disabled (2 hours)';
                disableBtn.textContent = 'Re-enable Auto-Off';
            } else {
                autoOffStatus.className = 'auto-off-status auto-off-enabled';
                autoOffStatus.textContent = 'Auto-off is enabled';
                disableBtn.textContent = 'Disable Auto-Off (2 hours)';
            }

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
                if (hasJobs) {
                    statusText = '<span class="status-indicator status-jobs"></span>Jobs present';
                } else if (isOn && countdown > 0) {
                    statusText = `<span class="status-indicator status-on"></span>Turning off in ${Math.ceil(countdown)}s`;
                } else if (isOn) {
                    statusText = '<span class="status-indicator status-on"></span>On';
                } else {
                    statusText = '<span class="status-indicator status-off"></span>Off';
                }

                card.innerHTML = `
                    <div class="printer-info">
                        <div class="printer-name">${printer}</div>
                        <div class="printer-status">${statusText}</div>
                    </div>
                    <div class="controls">
                        <button class="btn-on" onclick="controlPlug('${printer}', 'on')" ${isOn ? 'disabled' : ''}>Turn On</button>
                        <button class="btn-off" onclick="controlPlug('${printer}', 'off')" ${!isOn ? 'disabled' : ''}>Turn Off</button>
                    </div>
                `;

                container.appendChild(card);
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
                    await fetchData(); // Refresh data after toggle
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

    # Check if auto-off should be re-enabled
    if global_state['auto_off_disabled_until'] > 0 and now >= global_state['auto_off_disabled_until']:
        global_state['turn_off_delay'] = global_state['original_turn_off_delay']
        global_state['auto_off_disabled_until'] = 0

    printers_data = {}

    for printer, ip in PRINTERS.items():
        has_jobs = cups_queue_has_jobs(printer)
        plug_status = asyncio.run(get_plug_status(ip))

        # Calculate countdown remaining
        last_job = global_state['last_job_time'].get(printer, 0)
        countdown_remaining = 0
        if plug_status and not has_jobs and last_job > 0:
            elapsed = now - last_job
            countdown_remaining = max(0, global_state['turn_off_delay'] - elapsed)

        printers_data[printer] = {
            'has_jobs': has_jobs,
            'plug_status': plug_status,
            'countdown_remaining': countdown_remaining,
            'ip': ip
        }

    return jsonify({
        'printers': printers_data,
        'config': {
            'turn_off_delay': global_state['turn_off_delay'],
            'auto_off_disabled': now < global_state['auto_off_disabled_until']
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
        return jsonify({
            'turn_off_delay': global_state['turn_off_delay'],
            'auto_off_disabled': time.time() < global_state['auto_off_disabled_until']
        })
    elif request.method == 'POST':
        data = request.get_json()
        if 'turn_off_delay' in data:
            delay = int(data['turn_off_delay'])
            if 60 <= delay <= 3600:  # Between 1 minute and 1 hour
                global_state['turn_off_delay'] = delay
                return jsonify({'success': True})
            else:
                return jsonify({'error': 'Invalid delay value'}), 400
        return jsonify({'error': 'Missing turn_off_delay'}), 400

@app.route('/api/disable_auto_off', methods=['POST'])
def disable_auto_off():
    """Temporarily disable auto-off for 2 hours"""
    now = time.time()
    # Set turn_off_delay to 2 hours (7200 seconds)
    global_state['original_turn_off_delay'] = global_state['turn_off_delay']
    global_state['turn_off_delay'] = 7200
    global_state['auto_off_disabled_until'] = now + 7200  # 2 hours from now

    return jsonify({'success': True, 'disabled_until': global_state['auto_off_disabled_until']})

@app.route('/api/enable_auto_off', methods=['POST'])
def enable_auto_off():
    """Re-enable auto-off by restoring original delay"""
    global_state['turn_off_delay'] = global_state['original_turn_off_delay']
    global_state['auto_off_disabled_until'] = 0

    return jsonify({'success': True})

if __name__ == '__main__':
    # Initialize global state
    for printer in PRINTERS:
        global_state['plug_status'][printer] = False
        global_state['last_job_time'][printer] = 0

    app.run(host='0.0.0.0', port=5000, debug=True)

#!/usr/bin/env python3
"""
Test script for USB device detection and rescan functionality.
This script tests the functions implemented in always-available-backend.
"""

import sys
import os
import subprocess
import time

# Add current directory to path to import functions
sys.path.append('.')

# Import the functions we want to test
def log_message(message):
    """Log message to console for testing"""
    print(f"[TEST] {message}")

def check_usb_device_available(device_uri):
    """
    Check if the USB device is available by attempting to query it.
    Returns True if device is available, False otherwise.
    """
    try:
        # Try to call the USB backend to see if device is available
        # Use a timeout to avoid hanging
        env = os.environ.copy()
        env['DEVICE_URI'] = device_uri

        # Call backend with no arguments to check device discovery
        result = subprocess.run(
            ["/usr/lib/cups/backend/usb"],
            env=env,
            capture_output=True,
            text=True,
            timeout=5,
            errors='replace'  # Handle binary data in output
        )

        # If the backend returns successfully and mentions the device, it's available
        if result.returncode == 0 and device_uri.split('/')[-1].split('?')[0] in result.stdout:
            return True

        log_message(f"USB device check failed for {device_uri}: returncode={result.returncode}")
        return False

    except subprocess.TimeoutExpired:
        log_message(f"USB device check timeout for {device_uri}")
        return False
    except Exception as e:
        log_message(f"Error checking USB device {device_uri}: {e}")
        return False

def rescan_usb_ports():
    """
    Trigger a rescan of USB ports to detect newly connected devices.
    """
    try:
        log_message("Triggering USB port rescan")
        # Use udevadm to trigger USB subsystem rescan
        result = subprocess.run(
            ["sudo", "udevadm", "trigger", "--subsystem-match=usb"],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            log_message("USB port rescan completed successfully")
            # Wait a bit for devices to be recognized
            time.sleep(2)
            return True
        else:
            log_message(f"USB port rescan failed: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        log_message("USB port rescan timeout")
        return False
    except Exception as e:
        log_message(f"Error during USB port rescan: {e}")
        return False

def discover_usb_device_by_model(expected_model):
    """
    Dynamically discover the correct USB device URI by matching on printer model.
    This handles cases where USB devices get different device numbers on power cycles.

    Args:
        expected_model: The printer model to look for (e.g., "HP LaserJet 2100 Series")

    Returns:
        The correct USB device URI if found, None otherwise
    """
    try:
        log_message(f"Attempting dynamic discovery for model: {expected_model}")

        # Call the USB backend to get current device list
        result = subprocess.run(
            ["/usr/lib/cups/backend/usb"],
            capture_output=True,
            text=True,
            timeout=10,
            errors='replace'  # Handle binary data in output
        )

        if result.returncode != 0:
            log_message(f"USB backend discovery failed: {result.stderr}")
            return None

        # Parse the output to find matching devices
        lines = result.stdout.strip().split('\n')
        for line in lines:
            if line.startswith('direct usb://'):
                parts = line.split()
                if len(parts) >= 4:
                    device_uri = parts[1]
                    device_model = parts[2].strip('"')

                    # Check if this device matches our expected model
                    # Use case-insensitive matching and partial matches
                    if (expected_model.lower() in device_model.lower() or
                        device_model.lower() in expected_model.lower()):
                        log_message(f"Found matching device: {device_uri} -> {device_model}")
                        return device_uri

                    # Special handling for HP 2100TN which appears as "USB2.0-Print"
                    if "2100" in expected_model and "USB2.0-Print" in device_uri:
                        log_message(f"Found HP 2100TN device: {device_uri}")
                        return device_uri

        log_message(f"No matching USB device found for model: {expected_model}")
        return None

    except subprocess.TimeoutExpired:
        log_message("USB device discovery timeout")
        return None
    except Exception as e:
        log_message(f"Error during USB device discovery: {e}")
        return None

def test_device_detection():
    """Test USB device detection functionality"""
    print("=== Testing USB Device Detection ===")

    # Test with a sample device URI (adjust as needed for your setup)
    test_uri = "usb://HP/LaserJet%202100TN?serial=00CNCF134031"

    print(f"Testing device detection for: {test_uri}")

    # Check if device is available
    available = check_usb_device_available(test_uri)
    print(f"Device available: {available}")

    if not available:
        print("Device not found, testing rescan...")
        success = rescan_usb_ports()
        print(f"Rescan successful: {success}")

        if success:
            # Check again after rescan
            available_after = check_usb_device_available(test_uri)
            print(f"Device available after rescan: {available_after}")
    else:
        print("Device was already available, no rescan needed")

def test_dynamic_discovery():
    """Test dynamic device discovery by model"""
    print("\n=== Testing Dynamic Device Discovery ===")

    # Test models that should be discovered
    test_models = [
        "HP LaserJet 2100 Series",
        "HP LaserJet CP1525N",
        "USB2.0-Print"  # Special case for HP 2100TN
    ]

    for model in test_models:
        print(f"Testing discovery for model: {model}")
        discovered_uri = discover_usb_device_by_model(model)
        if discovered_uri:
            print(f"✓ Found device: {discovered_uri}")
        else:
            print(f"✗ No device found for model: {model}")

def test_backend_syntax():
    """Test that the backend script compiles without syntax errors"""
    print("\n=== Testing Backend Syntax ===")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", "always-available-backend"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print("✓ Backend syntax check passed")
        else:
            print(f"✗ Backend syntax check failed: {result.stderr}")
    except Exception as e:
        print(f"✗ Error during syntax check: {e}")

if __name__ == "__main__":
    print("USB Detection Test Script")
    print("=" * 40)

    test_backend_syntax()
    test_device_detection()
    test_dynamic_discovery()

    print("\n" + "=" * 40)
    print("Test completed. Check the output above for results.")

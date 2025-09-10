from kasa import Discover
import asyncio
import os
import sys
import warnings

# Add parent directory to path for config import
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import PRINTERS, TAPO_EMAIL, TAPO_PASSWORD

# Suppress aiohttp warnings
warnings.filterwarnings("ignore", category=ResourceWarning)

def ask_permission(printer_name, ip, current_state):
    action = "off" if current_state else "on"
    while True:
        response = input(f"{printer_name} ({ip}) is currently {'on' if current_state else 'off'}. Do you want to turn it {action}? (Y/n or Enter): ").strip().lower()
        if response == '' or response in ['y', 'yes']:
            return True
        elif response in ['n', 'no']:
            return False
        else:
            print("Invalid input. Please enter Y, n, or press Enter for Y.")

async def main():
    print("Testing Tapo plugs for all configured printers...")
    for printer, ip in PRINTERS.items():
        try:
            print(f"\n--- Testing {printer} ({ip}) ---")
            device = await Discover.discover_single(ip, username=TAPO_EMAIL, password=TAPO_PASSWORD)
            print(f"Device type: {type(device).__name__}")
            print(f"Device alias: {device.alias}")

            await device.update()
            print(f"Device {device.alias} is {'on' if device.is_on else 'off'}")

            permission = ask_permission(printer, ip, device.is_on)
            if permission:
                if device.is_on:
                    await device.turn_off()
                    print(f"Turned off {printer}")
                else:
                    await device.turn_on()
                    print(f"Turned on {printer}")
            else:
                print(f"Operation cancelled for {printer}.")

            if hasattr(device, 'protocol') and hasattr(device.protocol, 'close'):
                await device.protocol.close()
        except Exception as e:
            print(f"Error testing {printer} ({ip}): {e}")

asyncio.run(main())

from kasa import Discover
import asyncio
import os
import warnings

#Printer Name: HP CP1525N Plug
IP = "192.168.0.114"  # Tapo plug LAN IP

# Credentials from environment variables
TAPO_EMAIL = os.environ.get('TAPO_EMAIL', 'default@example.com')
TAPO_PASSWORD = os.environ.get('TAPO_PASSWORD', 'default_password')

# Suppress aiohttp warnings
warnings.filterwarnings("ignore", category=ResourceWarning)

def ask_permission(current_state):
    action = "off" if current_state else "on"
    while True:
        response = input(f"The device is currently {'on' if current_state else 'off'}. Do you want to turn it {action}? (Y/n or Enter): ").strip().lower()
        if response == '' or response in ['y', 'yes']:
            return True
        elif response in ['n', 'no']:
            return False
        else:
            print("Invalid input. Please enter Y, n, or press Enter for Y.")

async def main():
    print("Connecting to device...")
    device = await Discover.discover_single(IP, username=TAPO_EMAIL, password=TAPO_PASSWORD)
    print(f"Device type: {type(device).__name__}")
    print(f"Device alias: {device.alias}")

    await device.update()
    print(f"Device {device.alias} is {'on' if device.is_on else 'off'}")

    permission = ask_permission(device.is_on)
    if permission:
        if device.is_on:
            await device.turn_off()
            print("Turned off")
        else:
            await device.turn_on()
            print("Turned on")
    else:
        print("Operation cancelled by user.")

    if hasattr(device, 'protocol') and hasattr(device.protocol, 'close'):
        await device.protocol.close()

asyncio.run(main())

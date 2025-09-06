from kasa import Discover
import asyncio
import os
import warnings

# Printer Name: HP CP1525N Plug
IP = "192.168.0.114"  # Tapo plug LAN IP

# Credentials from environment variables
TAPO_EMAIL = os.environ.get('TAPO_EMAIL', 'default@example.com')
TAPO_PASSWORD = os.environ.get('TAPO_PASSWORD', 'default_password')

# Suppress aiohttp warnings
warnings.filterwarnings("ignore", category=ResourceWarning)

async def main():
    print("Connecting to device...")
    plug = await Discover.discover_single(IP, username=TAPO_EMAIL, password=TAPO_PASSWORD)
    await plug.update()
    print(f"Device {plug.alias} is {'on' if plug.is_on else 'off'}")

    if plug.is_on:
        await plug.turn_off()
        print("Turned off")
    else:
        await plug.turn_on()
        print("Turned on")

    if hasattr(plug, 'protocol') and hasattr(plug.protocol, 'close'):
        await plug.protocol.close()

asyncio.run(main())

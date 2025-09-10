from kasa import Discover
import asyncio
import os
import sys
import warnings

# Add parent directory to path for config import
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import PRINTERS, TAPO_EMAIL, TAPO_PASSWORD

# Printer Name: HP CP1525N Plug
IP = PRINTERS["HP_LaserJet_CP1525N"]  # Tapo plug LAN IP

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

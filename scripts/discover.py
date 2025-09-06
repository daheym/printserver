import asyncio
from kasa import Discover

async def main():
    print("Discovering Kasa/Tapo devices...")
    devices = await Discover.discover()
    print(f"Found {len(devices)} devices:")
    for ip, dev in devices.items():
        print(f"{ip}: {dev.alias} ({type(dev).__name__})")

asyncio.run(main())

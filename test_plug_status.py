#!/usr/bin/env python3
import asyncio
import os
import sys

# Add parent directory to path for config import
sys.path.append(os.path.dirname(__file__))
from config import PRINTERS, TAPO_EMAIL, TAPO_PASSWORD
from kasa import Discover

async def test_plug_status(ip):
    """Test plug status detection"""
    try:
        print(f"Testing plug at {ip}...")
        plug = await Discover.discover_single(ip, username=TAPO_EMAIL, password=TAPO_PASSWORD)
        await plug.update()
        status = plug.is_on
        alias = getattr(plug, 'alias', 'Unknown')
        print(f"Plug {ip} ({alias}): {'ON' if status else 'OFF'}")
        if hasattr(plug, 'protocol') and hasattr(plug.protocol, 'close'):
            await plug.protocol.close()
        return status
    except Exception as e:
        print(f"Error getting plug status for {ip}: {e}")
        return False

async def main():
    print(f"Using credentials: {TAPO_EMAIL}")
    for printer, ip in PRINTERS.items():
        status = await test_plug_status(ip)
        print(f"{printer}: {'ON' if status else 'OFF'}")

if __name__ == "__main__":
    asyncio.run(main())

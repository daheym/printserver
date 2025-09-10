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

async def get_energy_for_printer(printer_name, ip):
    print(f"\n--- Testing energy for {printer_name} ({ip}) ---")
    try:
        print("Connecting to device...")
        plug = await Discover.discover_single(ip, username=TAPO_EMAIL, password=TAPO_PASSWORD)
        await plug.update()

        print(f"Device {plug.alias} is {'on' if plug.is_on else 'off'}")

        # Get energy usage
        energy_log = ""
        try:
            await plug.update()

            if "Energy" in plug.modules:
                energy_module = plug.modules["Energy"]
                # print(f"Energy module found: {energy_module}")
                data = await energy_module.get_status()
                current_w = getattr(data, 'power', 0.0)
                total_kwh = 0.0

                # Get consumption data
                if hasattr(energy_module, 'consumption_today'):
                    today_kwh = energy_module.consumption_today
                    if today_kwh and today_kwh > 0:
                        total_kwh = today_kwh
                elif hasattr(energy_module, 'consumption_this_month'):
                    month_kwh = energy_module.consumption_this_month
                    if month_kwh and month_kwh > 0:
                        total_kwh = month_kwh

                energy_log = f" | Power Now: {current_w:.2f} W | Total: {total_kwh:.3f} kWh"
                print(f"Energy data: {energy_log}")
            else:
                print("Energy data not available (no Energy module)")
                print("Available modules:", list(plug.modules.keys()))
        except Exception as e:
            energy_log = f" | Energy data not available ({e})"
            print(f"Error getting energy data: {e}")
            import traceback
            traceback.print_exc()

        if hasattr(plug, 'protocol') and hasattr(plug.protocol, 'close'):
            await plug.protocol.close()
    except Exception as e:
        print(f"Error connecting to {printer_name} ({ip}): {e}")

async def main():
    print("Testing energy usage for all configured printers...")
    for printer, ip in PRINTERS.items():
        await get_energy_for_printer(printer, ip)

asyncio.run(main())

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

asyncio.run(main())

#!/usr/bin/env python3
import asyncio
import datetime
import os
import time
import subprocess
from kasa import Discover

# ===== CONFIGURATION =====
# Map CUPS printer name -> Tapo plug IP
PRINTERS = {
    "HP_LaserJet_CP1525N": "192.168.0.114",
    # "Lexmark_Optra_N": "192.168.0.115",
    "HP_Laserjet_2100TN": "192.168.0.116"
}

# Credentials
TAPO_EMAIL = os.environ.get('TAPO_EMAIL', 'default@example.com')
TAPO_PASSWORD = os.environ.get('TAPO_PASSWORD', 'default_password')

# Timing
CHECK_INTERVAL = 30     # seconds between CUPS checks
TURN_OFF_DELAY = 600     # seconds after last job before power off


# ===== FUNCTIONS =====
def cups_queue_has_jobs(printer_name):
    """Check if there are jobs in a CUPS printer queue"""
    result = subprocess.run(
        ["lpstat", "-o", printer_name], capture_output=True, text=True
    )
    return bool(result.stdout.strip())


async def turn_on(ip, printer):
    plug = await Discover.discover_single(ip, username=TAPO_EMAIL, password=TAPO_PASSWORD)
    await plug.update()
    if not plug.is_on:
        await plug.turn_on()
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {printer}: Turning ON plug {ip}")
    if hasattr(plug, 'protocol') and hasattr(plug.protocol, 'close'):
        await plug.protocol.close()


async def get_energy_data(plug):
    """Get energy consumption data from plug"""
    try:
        if "Energy" in plug.modules:
            energy_module = plug.modules["Energy"]
            data = await energy_module.get_status()
            current_w = getattr(data, 'power', 0.0)

            total_kwh = 0.0
            if hasattr(energy_module, 'consumption_today'):
                today_kwh = energy_module.consumption_today
                if today_kwh and today_kwh > 0:
                    total_kwh = today_kwh
            elif hasattr(energy_module, 'consumption_this_month'):
                month_kwh = energy_module.consumption_this_month
                if month_kwh and month_kwh > 0:
                    total_kwh = month_kwh

            return current_w, total_kwh
    except Exception as e:
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Error getting energy data: {e}")
    return 0.0, 0.0


async def turn_off(ip, printer):
    plug = await Discover.discover_single(ip, username=TAPO_EMAIL, password=TAPO_PASSWORD)
    await plug.update()
    if plug.is_on:
        # Get energy data before turning off
        current_w, total_kwh = await get_energy_data(plug)

        await plug.turn_off()
        energy_info = f" | Energy: {current_w:.2f} W | Total: {total_kwh:.3f} kWh" if total_kwh > 0 else ""
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {printer}: Turning OFF plug {ip}{energy_info}")
    if hasattr(plug, 'protocol') and hasattr(plug.protocol, 'close'):
        await plug.protocol.close()


# ===== MAIN LOOP =====
async def main():
    plug_status = {}
    last_job_time = {}

    # Initialize plug states
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Initializing printer states...")
    for printer, ip in PRINTERS.items():
        try:
            plug = await Discover.discover_single(ip, username=TAPO_EMAIL, password=TAPO_PASSWORD)
            await plug.update()
            is_on = plug.is_on
            plug_status[printer] = is_on
            has_jobs = cups_queue_has_jobs(printer)
            if is_on:
                if has_jobs:
                    last_job_time[printer] = time.time()
                    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {printer}: ON (jobs present)")
                else:
                    last_job_time[printer] = time.time()  # Start countdown immediately
                    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {printer}: ON (no jobs, starting countdown)")
            else:
                last_job_time[printer] = 0
                print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {printer}: OFF")
            if hasattr(plug, 'protocol') and hasattr(plug.protocol, 'close'):
                await plug.protocol.close()
        except Exception as e:
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Error initializing {printer}: {e}")
            plug_status[printer] = False
            last_job_time[printer] = 0

    while True:
        now = time.time()
        for printer, ip in PRINTERS.items():
            has_jobs = cups_queue_has_jobs(printer)
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Checking {printer}: {'jobs present' if has_jobs else 'no jobs'}")

            if has_jobs and not plug_status[printer]:
                await turn_on(ip, printer)
                plug_status[printer] = True
                last_job_time[printer] = now

            elif plug_status[printer] and not has_jobs:
                remaining = TURN_OFF_DELAY - (now - last_job_time[printer])
                if remaining > 0:
                    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {printer}: No jobs, turning off in {int(remaining)} seconds")
                else:
                    await turn_off(ip, printer)
                    plug_status[printer] = False

            elif has_jobs and plug_status[printer]:
                last_job_time[printer] = now

        await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
import asyncio
import datetime
import os
import time
import subprocess
from kasa import SmartPlug

# ===== CONFIGURATION =====
# Map CUPS printer name -> Tapo plug IP
PRINTERS = {
    # "Lexmark_Optra": "192.168.1.151",
    "HP_LaserJet_CP1525N": "192.168.0.114",
    # "HP_Serial": "192.168.1.153"
}

# Credentials
TAPO_EMAIL = os.environ.get('TAPO_EMAIL', 'default@example.com')
TAPO_PASSWORD = os.environ.get('TAPO_PASSWORD', 'default_password')

# Timing
CHECK_INTERVAL = 10     # seconds between CUPS checks
TURN_OFF_DELAY = 600     # seconds after last job before power off


# ===== FUNCTIONS =====
def cups_queue_has_jobs(printer_name):
    """Check if there are jobs in a CUPS printer queue"""
    result = subprocess.run(
        ["lpstat", "-o", printer_name], capture_output=True, text=True
    )
    return bool(result.stdout.strip())


async def turn_on(ip, printer):
    plug = SmartPlug(ip, username=TAPO_EMAIL, password=TAPO_PASSWORD)
    await plug.update()
    if not plug.is_on:
        await plug.turn_on()
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {printer}: Turning ON plug {ip}")
    if hasattr(plug, 'protocol') and hasattr(plug.protocol, 'close'):
        await plug.protocol.close()


async def turn_off(ip, printer):
    plug = SmartPlug(ip, username=TAPO_EMAIL, password=TAPO_PASSWORD)
    await plug.update()
    if plug.is_on:
        await plug.turn_off()
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {printer}: Turning OFF plug {ip}")
    if hasattr(plug, 'protocol') and hasattr(plug.protocol, 'close'):
        await plug.protocol.close()


# ===== MAIN LOOP =====
async def main():
    plug_status = {printer: False for printer in PRINTERS}
    last_job_time = {printer: 0 for printer in PRINTERS}

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
                if now - last_job_time[printer] > TURN_OFF_DELAY:
                    await turn_off(ip, printer)
                    plug_status[printer] = False

            elif has_jobs and plug_status[printer]:
                last_job_time[printer] = now

        await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())

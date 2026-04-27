#!/usr/bin/env python3
import asyncio
import datetime
import os
import sys
import time
import subprocess
from kasa import Discover

# Add parent directory to path for config import
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import PRINTERS, TAPO_EMAIL, TAPO_PASSWORD
from runtime_config import (
    disable_auto_off_for_job,
    get_auto_off_disable_users,
    get_turn_off_delay,
    has_auto_off_triggered_job,
    is_auto_off_disabled,
)
from send_mail import send_print_job_notification

# Timing
CHECK_INTERVAL = 30     # seconds between CUPS checks

# ===== FUNCTIONS =====
def cups_queue_has_jobs(printer_name):
    """Check if there are jobs in a CUPS printer queue"""
    result = subprocess.run(
        ["lpstat", "-o", printer_name], capture_output=True, text=True
    )
    return bool(result.stdout.strip())


def normalize_username(username):
    return str(username).strip().lower()


def parse_printer_job(printer_job):
    if "-" not in printer_job:
        return None, None
    return printer_job.rsplit("-", 1)


def get_job_signature(job):
    return (
        f"{job.get('printer', '')}-"
        f"{job.get('job_id', '')}-"
        f"{normalize_username(job.get('user', ''))}"
    )


def get_pending_jobs():
    jobs = []
    try:
        result = subprocess.run(["lpstat", "-o"], capture_output=True, text=True)
        if result.stdout.strip():
            for line in result.stdout.strip().splitlines():
                parts = line.split()
                if len(parts) < 4:
                    continue
                printer_name, job_id = parse_printer_job(parts[0])
                if not printer_name or not job_id:
                    continue
                jobs.append(
                    {
                        "printer": printer_name,
                        "job_id": job_id,
                        "user": parts[1],
                    }
                )
    except Exception as e:
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Error getting pending jobs: {e}")
        sys.stdout.flush()
    return jobs


def maybe_disable_auto_off_for_allowed_users(pending_jobs):
    allowed_users = {
        normalize_username(user)
        for user in get_auto_off_disable_users()
        if str(user).strip()
    }
    if not allowed_users:
        return None

    for job in pending_jobs:
        normalized_user = normalize_username(job.get("user", ""))
        if normalized_user not in allowed_users:
            continue

        job_signature = get_job_signature(job)
        try:
            if has_auto_off_triggered_job(job_signature):
                continue
            disable_auto_off_for_job(job_signature)
            print(
                f"[{datetime.datetime.now().strftime('%H:%M:%S')}] "
                f"Auto-off disabled because user '{job.get('user', '')}' submitted "
                f"job {job.get('printer', '')}-{job.get('job_id', '')}"
            )
            sys.stdout.flush()
            return job
        except ValueError:
            return None
        except Exception as e:
            print(
                f"[{datetime.datetime.now().strftime('%H:%M:%S')}] "
                f"Error auto-disabling auto-off for {job_signature}: {e}"
            )
            sys.stdout.flush()
            return None

    return None


def notify_for_new_jobs(pending_jobs, known_job_signatures):
    current_job_signatures = {get_job_signature(job) for job in pending_jobs}

    for job in pending_jobs:
        job_signature = get_job_signature(job)
        if job_signature in known_job_signatures:
            continue

        try:
            sent, message = send_print_job_notification(job)
            status = "sent" if sent else "skipped"
            print(
                f"[{datetime.datetime.now().strftime('%H:%M:%S')}] "
                f"Mail notification {status} for {job.get('printer', '')}-{job.get('job_id', '')}: {message}"
            )
        except Exception as e:
            print(
                f"[{datetime.datetime.now().strftime('%H:%M:%S')}] "
                f"Error sending mail notification for {job.get('printer', '')}-{job.get('job_id', '')}: {e}"
            )
        sys.stdout.flush()

    known_job_signatures.clear()
    known_job_signatures.update(current_job_signatures)


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


async def update_plug_statuses(plug_status):
    """Update plug_status dict with actual plug states"""
    for printer, ip in PRINTERS.items():
        try:
            plug = await Discover.discover_single(ip, username=TAPO_EMAIL, password=TAPO_PASSWORD)
            await plug.update()
            plug_status[printer] = plug.is_on
            if hasattr(plug, 'protocol') and hasattr(plug.protocol, 'close'):
                await plug.protocol.close()
        except Exception as e:
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Error updating status for {printer}: {e}")


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
    known_job_signatures = set()
    auto_off_was_disabled = is_auto_off_disabled()

    # Initialize plug states
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Initializing printer states...")
    sys.stdout.flush()
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
            sys.stdout.flush()
            if hasattr(plug, 'protocol') and hasattr(plug.protocol, 'close'):
                await plug.protocol.close()
        except Exception as e:
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Error initializing {printer}: {e}")
            sys.stdout.flush()
            plug_status[printer] = False
            last_job_time[printer] = 0

    while True:
        # Store previous plug states to detect manual activations
        previous_plug_status = plug_status.copy()

        # Update plug statuses with actual states
        await update_plug_statuses(plug_status)
        pending_jobs = get_pending_jobs()
        maybe_disable_auto_off_for_allowed_users(pending_jobs)
        notify_for_new_jobs(pending_jobs, known_job_signatures)

        now = time.time()
        current_auto_off_disabled = is_auto_off_disabled(now)
        if auto_off_was_disabled and not current_auto_off_disabled:
            current_turn_off_delay = get_turn_off_delay()
            for printer in PRINTERS:
                has_jobs = any(job["printer"] == printer for job in pending_jobs)
                if plug_status.get(printer, False) and not has_jobs:
                    last_job_time[printer] = now
                    print(
                        f"[{datetime.datetime.now().strftime('%H:%M:%S')}] "
                        f"{printer}: Auto-off re-enabled, starting {current_turn_off_delay}s countdown"
                    )
                    sys.stdout.flush()
        auto_off_was_disabled = current_auto_off_disabled

        for printer, ip in PRINTERS.items():
            has_jobs = any(job["printer"] == printer for job in pending_jobs)
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Checking {printer}: {'jobs present' if has_jobs else 'no jobs'}")
            sys.stdout.flush()

            if has_jobs and not plug_status[printer]:
                await turn_on(ip, printer)
                plug_status[printer] = True
                last_job_time[printer] = now

            elif plug_status[printer] and not has_jobs:
                # Read the latest runtime config so dashboard updates apply live.
                current_turn_off_delay = get_turn_off_delay()

                if current_auto_off_disabled:
                    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {printer}: Auto-off is disabled, keeping printer ON")
                    sys.stdout.flush()
                    continue

                # Detect manual activation: plug was off, now on
                if not previous_plug_status.get(printer, False) and plug_status[printer]:
                    last_job_time[printer] = now
                    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {printer}: Manual activation detected, starting {current_turn_off_delay}s countdown")
                    sys.stdout.flush()

                remaining = current_turn_off_delay - (now - last_job_time[printer])
                if remaining > 0:
                    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {printer}: No jobs, turning off in {int(remaining)} seconds")
                    sys.stdout.flush()
                else:
                    await turn_off(ip, printer)
                    plug_status[printer] = False
                    last_job_time[printer] = 0  # Reset for next activation

            elif has_jobs and plug_status[printer]:
                last_job_time[printer] = now

        await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())

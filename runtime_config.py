import json
import os
import tempfile
import time

from config import (
    AUTO_OFF_DISABLE_USERS as DEFAULT_AUTO_OFF_DISABLE_USERS,
    TURN_OFF_DELAY as DEFAULT_TURN_OFF_DELAY,
)


RUNTIME_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "runtime_config.json")
AUTO_OFF_TRIGGER_HISTORY_PATH = os.path.join(
    os.path.dirname(__file__), "auto_off_triggered_jobs.json"
)
AUTO_OFF_DISABLE_DURATION = 2 * 60 * 60
AUTO_OFF_TRIGGER_HISTORY_LIMIT = 20


def _normalize_user_list(users):
    normalized = []
    if not isinstance(users, list):
        return normalized

    seen = set()
    for user in users:
        if not isinstance(user, str):
            continue
        cleaned = user.strip().lower()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        normalized.append(cleaned)
    return normalized


def _normalize_triggered_jobs(triggered_jobs):
    normalized = []
    if not isinstance(triggered_jobs, list):
        return normalized

    seen = set()
    for signature in triggered_jobs:
        if not isinstance(signature, str):
            continue
        cleaned = signature.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        normalized.append(cleaned)
    return normalized[-AUTO_OFF_TRIGGER_HISTORY_LIMIT:]


def _default_config():
    return {
        "turn_off_delay": DEFAULT_TURN_OFF_DELAY,
        "auto_off_disabled_until": 0,
        "auto_off_disable_duration": AUTO_OFF_DISABLE_DURATION,
        "auto_off_disable_users": _normalize_user_list(DEFAULT_AUTO_OFF_DISABLE_USERS),
        "auto_off_last_trigger": None,
    }


def _atomic_write_json(path, data, prefix):
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)

    fd, temp_path = tempfile.mkstemp(
        prefix=prefix,
        suffix=".json",
        dir=directory,
        text=True,
    )

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def load_auto_off_triggered_jobs():
    try:
        with open(AUTO_OFF_TRIGGER_HISTORY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return []
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        return []

    return _normalize_triggered_jobs(data)


def save_auto_off_triggered_jobs(triggered_jobs):
    normalized = _normalize_triggered_jobs(triggered_jobs)
    _atomic_write_json(
        AUTO_OFF_TRIGGER_HISTORY_PATH,
        normalized,
        prefix=".auto_off_triggered_jobs.",
    )
    return normalized


def load_runtime_config():
    config = _default_config()

    try:
        with open(RUNTIME_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return config
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        return config

    if isinstance(data, dict):
        turn_off_delay = data.get("turn_off_delay", config["turn_off_delay"])
        auto_off_disabled_until = data.get(
            "auto_off_disabled_until", config["auto_off_disabled_until"]
        )
        auto_off_disable_duration = data.get(
            "auto_off_disable_duration", config["auto_off_disable_duration"]
        )
        auto_off_disable_users = data.get(
            "auto_off_disable_users", config["auto_off_disable_users"]
        )
        auto_off_last_trigger = data.get(
            "auto_off_last_trigger", config["auto_off_last_trigger"]
        )

        try:
            config["turn_off_delay"] = int(turn_off_delay)
        except (TypeError, ValueError):
            pass

        try:
            config["auto_off_disabled_until"] = int(auto_off_disabled_until)
        except (TypeError, ValueError):
            pass

        try:
            config["auto_off_disable_duration"] = max(1, int(auto_off_disable_duration))
        except (TypeError, ValueError):
            pass

        config["auto_off_disable_users"] = _normalize_user_list(auto_off_disable_users)
        if isinstance(auto_off_last_trigger, dict):
            config["auto_off_last_trigger"] = auto_off_last_trigger

        legacy_triggered_jobs = _normalize_triggered_jobs(
            data.get("auto_off_triggered_jobs", [])
        )
        if legacy_triggered_jobs and not load_auto_off_triggered_jobs():
            save_auto_off_triggered_jobs(legacy_triggered_jobs)

    return config


def save_runtime_config(config):
    normalized = _default_config()
    normalized["turn_off_delay"] = int(
        config.get("turn_off_delay", normalized["turn_off_delay"])
    )
    normalized["auto_off_disabled_until"] = int(
        config.get(
            "auto_off_disabled_until",
            normalized["auto_off_disabled_until"],
        )
    )
    normalized["auto_off_disable_duration"] = max(
        1,
        int(
            config.get(
                "auto_off_disable_duration",
                normalized["auto_off_disable_duration"],
            )
        ),
    )
    normalized["auto_off_disable_users"] = _normalize_user_list(
        config.get("auto_off_disable_users", normalized["auto_off_disable_users"])
    )
    auto_off_last_trigger = config.get("auto_off_last_trigger")
    normalized["auto_off_last_trigger"] = (
        auto_off_last_trigger if isinstance(auto_off_last_trigger, dict) else None
    )
    _atomic_write_json(RUNTIME_CONFIG_PATH, normalized, prefix=".runtime_config.")

    return normalized


def get_turn_off_delay():
    return load_runtime_config()["turn_off_delay"]


def set_turn_off_delay(delay):
    config = load_runtime_config()
    config["turn_off_delay"] = int(delay)
    return save_runtime_config(config)


def get_auto_off_disabled_until():
    return load_runtime_config()["auto_off_disabled_until"]


def get_auto_off_disable_duration():
    return load_runtime_config()["auto_off_disable_duration"]


def set_auto_off_disable_duration(duration_seconds):
    config = load_runtime_config()
    config["auto_off_disable_duration"] = max(1, int(duration_seconds))
    return save_runtime_config(config)


def get_auto_off_disable_users():
    return load_runtime_config()["auto_off_disable_users"]


def set_auto_off_disable_users(users):
    config = load_runtime_config()
    config["auto_off_disable_users"] = _normalize_user_list(users)
    return save_runtime_config(config)


def has_auto_off_triggered_job(job_signature):
    cleaned_signature = str(job_signature).strip()
    if not cleaned_signature:
        return False
    return cleaned_signature in load_auto_off_triggered_jobs()


def is_auto_off_disabled(now=None):
    if now is None:
        now = time.time()
    return get_auto_off_disabled_until() > now


def disable_auto_off(duration_seconds=AUTO_OFF_DISABLE_DURATION, now=None):
    if now is None:
        now = time.time()

    config = load_runtime_config()
    if duration_seconds == AUTO_OFF_DISABLE_DURATION:
        duration_seconds = config["auto_off_disable_duration"]
    config["auto_off_disabled_until"] = int(now + duration_seconds)
    config["auto_off_last_trigger"] = None
    return save_runtime_config(config)


def disable_auto_off_for_job(job_signature, duration_seconds=AUTO_OFF_DISABLE_DURATION, now=None):
    if now is None:
        now = time.time()

    cleaned_signature = str(job_signature).strip()
    if not cleaned_signature:
        raise ValueError("job_signature must not be empty")

    config = load_runtime_config()
    if duration_seconds == AUTO_OFF_DISABLE_DURATION:
        duration_seconds = config["auto_off_disable_duration"]

    triggered_jobs = load_auto_off_triggered_jobs()
    if cleaned_signature in triggered_jobs:
        return config

    triggered_jobs.append(cleaned_signature)
    save_auto_off_triggered_jobs(triggered_jobs)
    config["auto_off_disabled_until"] = int(now + duration_seconds)
    printer_name, job_id = cleaned_signature.rsplit("-", 2)[:2]
    config["auto_off_last_trigger"] = {
        "source": "user_job",
        "job_signature": cleaned_signature,
        "printer": printer_name,
        "job_id": job_id,
        "user": cleaned_signature.rsplit("-", 1)[-1],
        "triggered_at": int(now),
    }
    return save_runtime_config(config)


def enable_auto_off():
    config = load_runtime_config()
    config["auto_off_disabled_until"] = 0
    config["auto_off_last_trigger"] = None
    return save_runtime_config(config)

import json
import os
import tempfile
import time

from config import TURN_OFF_DELAY as DEFAULT_TURN_OFF_DELAY


RUNTIME_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "runtime_config.json")
AUTO_OFF_DISABLE_DURATION = 2 * 60 * 60


def _default_config():
    return {
        "turn_off_delay": DEFAULT_TURN_OFF_DELAY,
        "auto_off_disabled_until": 0,
        "auto_off_disable_duration": AUTO_OFF_DISABLE_DURATION,
    }


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

    directory = os.path.dirname(RUNTIME_CONFIG_PATH)
    os.makedirs(directory, exist_ok=True)

    fd, temp_path = tempfile.mkstemp(
        prefix=".runtime_config.",
        suffix=".json",
        dir=directory,
        text=True,
    )

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(normalized, f, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(temp_path, RUNTIME_CONFIG_PATH)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)

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
    return save_runtime_config(config)


def enable_auto_off():
    config = load_runtime_config()
    config["auto_off_disabled_until"] = 0
    return save_runtime_config(config)

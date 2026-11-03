"""
Settings Store Module
---------------------------
Lets API keys be entered from the web UI's Settings panel instead of
requiring the user to edit .env or any code. Keys saved this way are
written to /config/api_keys.json (created on first save; gitignored) and
always take priority over the equivalent environment variable, so both
paths keep working side by side.

This file is intentionally dependency-free (stdlib only) so every other
module — including the numbered core_engine files loaded via importlib —
can import it with a plain `from core_engine.settings_store import ...`
with no circular-import risk.
"""

import os
import json
import threading

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SETTINGS_PATH = os.path.join(_BASE_DIR, "config", "api_keys.json")
_lock = threading.Lock()


def _load() -> dict:
    if not os.path.exists(_SETTINGS_PATH):
        return {}
    try:
        with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def get_setting(key: str, env_fallback: str = None) -> str:
    """Returns the saved value for `key` if one was set via the UI,
    otherwise falls back to the `env_fallback` environment variable
    (if given), otherwise an empty string."""
    value = _load().get(key, "")
    if value:
        return value
    if env_fallback:
        return os.getenv(env_fallback, "")
    return ""


def save_settings(**fields) -> dict:
    """Saves one or more fields. A field passed as None is left
    unchanged; pass an empty string explicitly to clear a field."""
    with _lock:
        data = _load()
        for key, value in fields.items():
            if value is None:
                continue
            data[key] = value.strip()
        os.makedirs(os.path.dirname(_SETTINGS_PATH), exist_ok=True)
        with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    return data


def mask(value: str) -> str:
    """Returns a display-safe masked form of a secret, e.g. 'AIza••••••7xQ'.
    Never send the raw value back to the frontend after it's saved."""
    if not value:
        return ""
    if len(value) <= 8:
        return "•" * len(value)
    return value[:4] + "•" * (len(value) - 8) + value[-4:]

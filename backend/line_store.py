"""Lightweight file-based storage for the LINE integration.

Keeps the MVP simple: no database, just two JSON files under backend/data/.
- reports.json    : { user_id: {report dict from analyze_ingredient, saved_at} }
- reminders.json  : { user_id: [{"time": "HH:MM", "note": str}, ...] }

Not safe for high concurrency, but fine for a hackathon-scale demo.
"""
import json
import os
import threading
import time

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
REPORTS_PATH = os.path.join(DATA_DIR, "reports.json")
REMINDERS_PATH = os.path.join(DATA_DIR, "reminders.json")

_lock = threading.Lock()


def _ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def _read_json(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _write_json(path: str, data: dict):
    _ensure_data_dir()
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


def save_report(user_id: str, report: dict):
    """Stores the most recent analysis report for a LINE user."""
    with _lock:
        data = _read_json(REPORTS_PATH)
        data[user_id] = {**report, "saved_at": time.time()}
        _write_json(REPORTS_PATH, data)


def get_latest_report(user_id: str) -> dict | None:
    """Returns the most recent analysis report for a LINE user, or None."""
    with _lock:
        data = _read_json(REPORTS_PATH)
        return data.get(user_id)


def add_reminder(user_id: str, time_str: str, note: str = "") -> dict:
    """Registers a daily medication reminder time (HH:MM) for a LINE user."""
    with _lock:
        data = _read_json(REMINDERS_PATH)
        user_reminders = data.setdefault(user_id, [])
        entry = {"time": time_str, "note": note}
        if entry not in user_reminders:
            user_reminders.append(entry)
        _write_json(REMINDERS_PATH, data)
        return entry


def list_all_reminders() -> dict:
    """Returns the full {user_id: [reminders]} map, for the reminder-push job."""
    with _lock:
        return _read_json(REMINDERS_PATH)


def get_reminders(user_id: str) -> list:
    """Returns the list of registered reminder times for one user."""
    with _lock:
        data = _read_json(REMINDERS_PATH)
        return data.get(user_id, [])


def clear_reminders(user_id: str, time_str: str | None = None) -> None:
    """Cancels reminders for a user: a specific HH:MM slot, or all of them if time_str is None."""
    with _lock:
        data = _read_json(REMINDERS_PATH)
        if user_id not in data:
            return
        if time_str is None:
            del data[user_id]
        else:
            data[user_id] = [e for e in data[user_id] if e.get("time") != time_str]
            if not data[user_id]:
                del data[user_id]
        _write_json(REMINDERS_PATH, data)

"""Lightweight file-based storage for the LINE integration.

Keeps the MVP simple: no database, just JSON files under backend/data/.
- reports.json     : { user_id: {report dict from analyze_ingredient, saved_at} }
- reminders.json   : { user_id: [{"time": "HH:MM", "note": str}, ...] }
- profiles.json    : { user_id: {"allergies": [str], "medications": [str]} }
- family_codes.json: { code: {"patient_user_id": str, "expires_at": float} }
- family_links.json: { patient_user_id: [family_user_id, ...] }
- dose_logs.json   : { user_id: [ "YYYY-MM-DD", ... ] }  (dates the user checked in)

Not safe for high concurrency, but fine for a hackathon-scale demo.
"""
import json
import os
import random
import string
import threading
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
REPORTS_PATH = os.path.join(DATA_DIR, "reports.json")
REMINDERS_PATH = os.path.join(DATA_DIR, "reminders.json")
PROFILES_PATH = os.path.join(DATA_DIR, "profiles.json")
FAMILY_CODES_PATH = os.path.join(DATA_DIR, "family_codes.json")
FAMILY_LINKS_PATH = os.path.join(DATA_DIR, "family_links.json")
DOSE_LOGS_PATH = os.path.join(DATA_DIR, "dose_logs.json")

TAIPEI_TZ = ZoneInfo("Asia/Taipei")

FAMILY_CODE_TTL = 600  # seconds a generated linking code stays valid

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


def save_profile(user_id: str, allergies: list, medications: list) -> dict:
    """Stores a LINE user's self-registered allergy/medication list."""
    with _lock:
        data = _read_json(PROFILES_PATH)
        profile = {"allergies": allergies, "medications": medications}
        data[user_id] = profile
        _write_json(PROFILES_PATH, data)
        return profile


def get_profile(user_id: str) -> dict | None:
    """Returns a LINE user's registered profile, or None if they haven't set one up."""
    with _lock:
        data = _read_json(PROFILES_PATH)
        return data.get(user_id)


def create_family_link_code(patient_user_id: str) -> str:
    """Generates a short-lived numeric code a family member can redeem to subscribe
    to this patient's allergy-alert notifications."""
    with _lock:
        data = _read_json(FAMILY_CODES_PATH)
        # Drop expired codes while we're at it.
        now = time.time()
        data = {c: v for c, v in data.items() if v.get("expires_at", 0) > now}
        code = "".join(random.choices(string.digits, k=6))
        while code in data:
            code = "".join(random.choices(string.digits, k=6))
        data[code] = {"patient_user_id": patient_user_id, "expires_at": now + FAMILY_CODE_TTL}
        _write_json(FAMILY_CODES_PATH, data)
        return code


def redeem_family_link_code(code: str, family_user_id: str) -> str | None:
    """Links family_user_id to the patient who generated this code. Returns the
    patient's user_id on success, or None if the code is invalid/expired."""
    with _lock:
        codes = _read_json(FAMILY_CODES_PATH)
        entry = codes.get(code)
        if not entry or entry.get("expires_at", 0) < time.time():
            return None
        patient_user_id = entry["patient_user_id"]
        del codes[code]
        _write_json(FAMILY_CODES_PATH, codes)

        links = _read_json(FAMILY_LINKS_PATH)
        members = links.setdefault(patient_user_id, [])
        if family_user_id not in members:
            members.append(family_user_id)
        _write_json(FAMILY_LINKS_PATH, links)
        return patient_user_id


def get_family_members(patient_user_id: str) -> list:
    """Returns the list of family user_ids subscribed to this patient's alerts."""
    with _lock:
        links = _read_json(FAMILY_LINKS_PATH)
        return links.get(patient_user_id, [])


def log_dose_taken(user_id: str) -> str:
    """Checks the user in as having taken their dose today (Asia/Taipei date).
    Idempotent: checking in twice on the same day only records one entry."""
    today = datetime.now(TAIPEI_TZ).strftime("%Y-%m-%d")
    with _lock:
        data = _read_json(DOSE_LOGS_PATH)
        dates = data.setdefault(user_id, [])
        if today not in dates:
            dates.append(today)
        _write_json(DOSE_LOGS_PATH, data)
        return today


def get_dose_log(user_id: str, days: int = 7) -> list:
    """Returns the last `days` days (oldest first) as {"date": "YYYY-MM-DD", "taken": bool}."""
    with _lock:
        data = _read_json(DOSE_LOGS_PATH)
        taken_dates = set(data.get(user_id, []))

    today = datetime.now(TAIPEI_TZ).date()
    return [
        {
            "date": (today - timedelta(days=offset)).strftime("%Y-%m-%d"),
            "taken": (today - timedelta(days=offset)).strftime("%Y-%m-%d") in taken_dates,
        }
        for offset in range(days - 1, -1, -1)
    ]

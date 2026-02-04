"""
Utility functions for Visual Patrol system.
Includes JSON I/O and timezone-aware time utilities.
"""

import os
import json
import tempfile
import shutil
from datetime import datetime
from zoneinfo import ZoneInfo


def _get_settings():
    """Get settings from database via settings_service."""
    import settings_service
    return settings_service.get_all()


def _get_timezone():
    """Get configured timezone, with fallback to UTC."""
    settings = _get_settings()
    tz_name = settings.get('timezone', 'UTC')
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo("UTC")


# === JSON I/O ===

def load_json(filepath, default=None):
    """Load JSON file with fallback to default value."""
    if default is None:
        default = {}
    if not os.path.exists(filepath):
        return default
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def save_json(filepath, data):
    """
    Atomically save JSON data to file.
    Uses temp file + rename to prevent corruption on crash.
    """
    dir_path = os.path.dirname(filepath)
    if dir_path and not os.path.exists(dir_path):
        os.makedirs(dir_path, exist_ok=True)

    fd, temp_path = tempfile.mkstemp(suffix='.json', dir=dir_path)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        shutil.move(temp_path, filepath)
    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise


# === Time Utilities ===

def get_current_time_str():
    """Returns current time as 'YYYY-MM-DD HH:MM:SS' in configured timezone."""
    return datetime.now(_get_timezone()).strftime("%Y-%m-%d %H:%M:%S")


def get_current_datetime():
    """Returns current datetime object in configured timezone."""
    return datetime.now(_get_timezone())


def get_filename_timestamp():
    """Returns current time as 'YYYYMMDD_HHMMSS' for filenames."""
    return datetime.now(_get_timezone()).strftime("%Y%m%d_%H%M%S")


# === Image Utilities ===

def rename_image_with_status(image_path, is_ng):
    """
    Rename image file to include OK/NG status.
    Example: image.jpg -> image_OK.jpg or image_NG.jpg
    """
    if not image_path or not os.path.exists(image_path):
        return image_path

    status_tag = "NG" if is_ng else "OK"
    base, ext = os.path.splitext(image_path)

    # Avoid double-tagging
    if base.endswith("_OK") or base.endswith("_NG"):
        return image_path

    new_path = f"{base}_{status_tag}{ext}"
    try:
        os.rename(image_path, new_path)
        return new_path
    except OSError:
        return image_path

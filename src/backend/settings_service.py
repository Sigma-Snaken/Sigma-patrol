"""
Settings Service - Wraps global_settings DB table.
Replaces file-based settings.json with shared DB storage.
"""

import json
import os
from config import DEFAULT_SETTINGS
from database import get_global_settings, save_global_settings


def get_all():
    """Get all settings merged with defaults."""
    return get_global_settings()


def get(key, default=None):
    """Get a single setting value."""
    settings = get_global_settings()
    if default is not None:
        return settings.get(key, default)
    return settings.get(key, DEFAULT_SETTINGS.get(key))


def save(settings_dict):
    """Save settings dict to DB."""
    save_global_settings(settings_dict)


def migrate_from_json(json_path):
    """One-time import from legacy settings.json into DB."""
    if not os.path.exists(json_path):
        return False

    # Check if DB already has settings (skip if already migrated)
    current = get_global_settings()
    # If any non-default key has been set, assume migration already happened
    has_custom = False
    for key in current:
        if key in DEFAULT_SETTINGS and current[key] != DEFAULT_SETTINGS[key]:
            has_custom = True
            break

    if has_custom:
        return False

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            file_settings = json.load(f)

        if isinstance(file_settings, dict) and file_settings:
            save_global_settings(file_settings)
            print(f"Migrated settings from {json_path} to database")
            return True
    except Exception as e:
        print(f"Settings migration warning: {e}")

    return False

import os
import json
import tempfile
import shutil

def load_json(filepath, default):
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
    Uses a temp file + rename to prevent corruption on crash.
    Raises exception on failure so caller can handle it.
    """
    dir_path = os.path.dirname(filepath)
    if dir_path and not os.path.exists(dir_path):
        os.makedirs(dir_path, exist_ok=True)

    # Write to temp file first, then atomically rename
    fd, temp_path = tempfile.mkstemp(suffix='.json', dir=dir_path)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        # Atomic rename (on POSIX systems)
        shutil.move(temp_path, filepath)
    except Exception:
        # Clean up temp file on failure
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise

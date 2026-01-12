from datetime import datetime
from zoneinfo import ZoneInfo
from config import SETTINGS_FILE, DEFAULT_SETTINGS
from utils import load_json

def get_current_time_str():
    """Returns current time formatted as YYYY-MM-DD HH:MM:SS in the configured timezone."""
    settings = load_json(SETTINGS_FILE, DEFAULT_SETTINGS)
    tz_name = settings.get('timezone', 'UTC')
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("UTC")
        
    now = datetime.now(tz)
    return now.strftime("%Y-%m-%d %H:%M:%S")

def get_current_datetime():
    """Returns current datetime object in the configured timezone."""
    settings = load_json(SETTINGS_FILE, DEFAULT_SETTINGS)
    tz_name = settings.get('timezone', 'UTC')
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("UTC")
    return datetime.now(tz)

def get_current_filename_time_str():
    """Returns current time formatted for filenames (YYYMMDD_HHMMSS) in configured timezone."""
    dt = get_current_datetime()
    return dt.strftime("%Y%m%d_%H%M%S")


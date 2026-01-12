import os

ROBOT_IP = "192.168.50.133:26400"

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.getenv("DATA_DIR", os.path.join(BASE_DIR, "data"))
LOG_DIR = os.getenv("LOG_DIR", os.path.join(BASE_DIR, "logs"))

CONFIG_DIR = os.path.join(DATA_DIR, "config")
REPORT_DIR = os.path.join(DATA_DIR, "report")
IMAGES_DIR = os.path.join(REPORT_DIR, "images")

POINTS_FILE = os.path.join(CONFIG_DIR, "points.json")
SETTINGS_FILE = os.path.join(CONFIG_DIR, "settings.json")
RESULTS_FILE = os.path.join(REPORT_DIR, "results.json")
DB_FILE = os.path.join(REPORT_DIR, "report.db")

DEFAULT_SETTINGS = {
    "gemini_api_key": "",
    "gemini_model": "gemini-2.5-flash",
    "system_prompt": "You are a helpful robot assistant. Analyze this image from my patrol.",
    "timezone": "UTC"
}

def ensure_dirs():
    os.makedirs(CONFIG_DIR, exist_ok=True)
    os.makedirs(REPORT_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(IMAGES_DIR, exist_ok=True)

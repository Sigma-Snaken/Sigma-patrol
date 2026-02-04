import logging
import os
from config import LOG_DIR, ROBOT_ID
from utils import get_current_datetime

class TimezoneFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        dt = get_current_datetime()
        if datefmt:
            return dt.strftime(datefmt)
        else:
            return dt.strftime('%Y-%m-%d %H:%M:%S')

def get_logger(name, log_file):
    # Prefix log filename with robot_id when not default
    if ROBOT_ID != "default":
        base, ext = os.path.splitext(log_file)
        log_file = f"{ROBOT_ID}_{base}{ext}"

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Check if handler already exists to avoid duplicate logs
    if not logger.handlers:
        formatter = TimezoneFormatter('%(asctime)s %(levelname)s: %(message)s')

        # File Handler
        file_handler = logging.FileHandler(os.path.join(LOG_DIR, log_file))
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # Stream Handler (to stdout for Docker)
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    return logger

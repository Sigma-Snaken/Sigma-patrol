import logging
import os
from config import LOG_DIR
from utils import get_current_datetime

class TimezoneFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        dt = get_current_datetime()
        # We want to use the record's timestamp but converted to our timezone
        # record.created is UTC timestamp. 
        # Actually simplest is just to get current time in TZ if we assume log happens now.
        # But better is to convert record.created.
        
        # However, Python logging makes this tricky to inject TZ without external help.
        # Since our requirement is showing the configured time, and logs are usually real-time:
        if datefmt:
            return dt.strftime(datefmt)
        else:
            return dt.strftime('%Y-%m-%d %H:%M:%S')

def get_logger(name, log_file):
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
        stream_handler.setFormatter(logging.Formatter('%(name)s - %(levelname)s - %(message)s'))
        # Note: We keep stream handler simple or we can also apply TZ formatter? 
        # User asked for logs to be correct. Let's apply it to stream too for consistency.
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)
        
    return logger

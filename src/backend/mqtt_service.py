"""
MQTT Service - Handles physiological sensor data collection via MQTT.
"""
import json
import logging
import os
import asyncio
import sqlite3
import uuid
import paho.mqtt.client as mqtt
from datetime import datetime
from config import DATA_DIR
from logger import get_logger

logger = get_logger("mqtt_service", "mqtt_service.log")

class BioSensorMQTTClient:
    def __init__(self, broker="localhost", port=1883, topic="/my/default/channel", db_path=None):
        self.broker = broker
        self.port = port
        self.topic = topic
        
        if db_path is None:
            self.db_path = os.path.join(DATA_DIR, "sensor_data.db")
        else:
            self.db_path = db_path

        self.client = mqtt.Client(protocol=mqtt.MQTTv311)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.latest_data = None
        self._init_database()
    
    def _init_database(self):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sensor_scan_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    bed_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    retry_count INTEGER NOT NULL,
                    status INTEGER,
                    bpm INTEGER,
                    rpm INTEGER,
                    data_json TEXT,
                    is_valid BOOLEAN DEFAULT FALSE,
                    details TEXT NULL
                )
            ''')
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to initialize sensor database: {e}")
    
    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info(f"Connected to MQTT Broker at {self.broker}:{self.port}")
            client.subscribe(self.topic)
            logger.info(f"Subscribed to topic: {self.topic}")
        else:
            logger.error(f"Failed to connect to MQTT Broker, return code {rc}")
    
    def _on_message(self, client, userdata, msg):
        try:
            payload = msg.payload.decode()
            # logger.debug(f"Received message: {payload}")
            self.latest_data = json.loads(payload)
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")
    
    def start(self):
        try:
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()
            logger.info("MQTT Client started")
        except Exception as e:
            logger.error(f"Failed to start MQTT client: {e}")

    def stop(self):
        try:
            self.client.loop_stop()
            self.client.disconnect()
            logger.info("MQTT Client stopped")
        except Exception as e:
            logger.error(f"Error stopping MQTT client: {e}")

    def _save_scan_data(self, task_id, data, retry_count, is_valid=False):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            timestamp = datetime.now().isoformat()
            cursor.execute('''
                INSERT INTO sensor_scan_data 
                (task_id, bed_id, timestamp, retry_count, status, bpm, rpm, data_json, is_valid, details)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                task_id,
                data.get('bed_id', 'Unknown'),
                timestamp,
                retry_count,
                data.get('status'),
                data.get('bpm'),
                data.get('rpm'),
                json.dumps(data),
                is_valid,
                data.get('details'),
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to save scan data: {e}")

    async def get_valid_scan_data(self, task_id=None, target_bed=None, settings=None):
        if task_id is None:
            task_id = str(uuid.uuid4())

        if settings is None:
            settings = {}

        # Use configurable values from settings, with defaults
        WAIT_TIME = settings.get('bio_scan_wait_time', 10)
        RETRY_COUNT = settings.get('bio_scan_retry_count', 6)
        INT_WAIT_TIME = settings.get('bio_scan_initial_wait', 5)
        VALID_STATUS = settings.get('bio_scan_valid_status', 4)

        valid_data = None

        logger.info(f"Starting bio scan for bed {target_bed}, task {task_id}")
        logger.info(f"Bio scan settings: wait={WAIT_TIME}s, retries={RETRY_COUNT}, initial={INT_WAIT_TIME}s, valid_status={VALID_STATUS}")
        await asyncio.sleep(INT_WAIT_TIME)

        for retry_count in range(RETRY_COUNT):
            if self.latest_data and 'records' in self.latest_data:
                # Filter specifically for the target bed if possible, or just take the latest valid record
                # The original code iterated through all records.

                # Assuming the sensor data stream might contain multiple beds or we just check the latest dump
                found_valid_in_batch = False

                for data in self.latest_data['records']:
                    # Logic to match bed_id if the sensor data provides it?
                    # Original code force-assigned target_bed to the data record.

                    # Check validity using configurable status code
                    is_valid = data.get('status') == VALID_STATUS and data.get('bpm', 0) > 0 and data.get('rpm', 0) > 0
                    
                    data['details'] = 'Normal Measurement' if is_valid else 'Invalid Measurement'
                    data['bed_id'] = target_bed # Assign context
                    
                    self._save_scan_data(f"{task_id}-{target_bed}-{retry_count}", data, retry_count, is_valid)
                    
                    if is_valid:
                        valid_data = data
                        found_valid_in_batch = True
                        break # Found a valid one in this batch
                
                if found_valid_in_batch:
                    logger.info(f"Valid scan data found for {target_bed}")
                    return {"task_id": task_id, "data": valid_data}
                    
            logger.info(f"No valid data yet for {target_bed}, retrying ({retry_count+1}/{RETRY_COUNT})...")
            if(retry_count + 1 < RETRY_COUNT):
                await asyncio.sleep(WAIT_TIME)
        
        logger.warning(f"Bio scan timed out for {target_bed}")
        return {"task_id": task_id, "data": None}

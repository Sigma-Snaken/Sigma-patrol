"""
Live Monitor - Background camera monitoring via VILA Alert API during patrol.
Continuously sends camera frames to VILA Alert API with configurable alert rules.
"""

import threading
import time
import base64
import os

import requests

from config import ROBOT_ID, ROBOT_DATA_DIR
from database import db_context
from logger import get_logger
from utils import get_current_time_str

logger = get_logger("live_monitor", "live_monitor.log")

def _call_vila_chat(vila_url, data_url, rules, timeout=30):
    """Call VILA chat completions once per rule (OpenAI-compatible).

    Sends one request per rule for reliable yes/no answers from small VLMs.
    Returns list of answer strings, one per rule.
    """
    url = f"{vila_url}/v1/chat/completions"
    answers = []

    for rule in rules:
        question = rule
        messages = []
        messages.append({
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": data_url}},
                {"type": "text", "text": question},
            ],
        })
        body = {
            "messages": messages,
            "max_tokens": 16,
        }

        try:
            resp = requests.post(url, json=body, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            answers.append(content.strip().rstrip(".").strip())
        except Exception as e:
            logger.error(f"VILA chat error for rule '{rule}': {e}")
            answers.append("")

    return answers


class LiveMonitor:
    """Background monitor: sends camera frames to VILA Alert API during patrol."""

    def __init__(self):
        self.is_monitoring = False
        self.monitor_thread = None
        self.check_interval = 5.0
        self.alert_rules = []
        self.current_run_id = None
        self.alerts = []
        self.alert_cooldowns = {}  # {rule: last_trigger_timestamp}
        self.cooldown_seconds = 60
        self._lock = threading.Lock()

    def start(self, run_id, alert_rules, vila_alert_url, frame_func, check_interval=5.0,
              telegram_config=None):
        """Start background monitoring.

        Args:
            run_id: Current patrol run ID.
            alert_rules: List of alert rule strings (questions).
            vila_alert_url: VILA alert endpoint base URL.
            frame_func: Callable returning camera image (gRPC response with .data).
            check_interval: Seconds between checks.
            telegram_config: Optional dict with keys: bot_token, user_id. If provided, alerts are sent to Telegram.
        """
        if self.is_monitoring:
            return

        self.current_run_id = run_id
        self.alert_rules = list(alert_rules)
        self.vila_alert_url = vila_alert_url.rstrip("/")
        self.frame_func = frame_func
        self.check_interval = check_interval
        self.telegram_config = telegram_config
        self.alerts = []
        self.alert_cooldowns = {}

        self.is_monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info(f"LiveMonitor started for run {run_id} with {len(alert_rules)} rules, interval={check_interval}s")

    def stop(self):
        """Stop background monitoring."""
        if not self.is_monitoring:
            return
        self.is_monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=10)
            self.monitor_thread = None
        logger.info(f"LiveMonitor stopped. Total alerts: {len(self.alerts)}")

    def get_alerts(self):
        """Return list of alerts collected during this run."""
        with self._lock:
            return list(self.alerts)

    def _monitor_loop(self):
        """Main monitoring loop running in background thread."""
        # Ensure evidence image directory exists
        evidence_dir = os.path.join(ROBOT_DATA_DIR, "report", "live_alerts")
        os.makedirs(evidence_dir, exist_ok=True)

        while self.is_monitoring:
            start_time = time.time()

            try:
                self._check_once(evidence_dir)
            except Exception as e:
                logger.error(f"LiveMonitor check error: {e}")

            elapsed = time.time() - start_time
            sleep_time = max(0, self.check_interval - elapsed)
            # Sleep in small increments so we can stop quickly
            end_sleep = time.time() + sleep_time
            while time.time() < end_sleep and self.is_monitoring:
                time.sleep(0.5)

    def _check_once(self, evidence_dir):
        """Capture frame, call VILA chat completions, process results."""
        # 1. Get camera frame
        img_response = self.frame_func()
        if not img_response or not img_response.data:
            return

        jpeg_bytes = img_response.data

        # 2. Base64 encode
        b64 = base64.b64encode(jpeg_bytes).decode()
        data_url = f"data:image/jpeg;base64,{b64}"

        # 3. Call VILA chat completions
        alert_responses = _call_vila_chat(self.vila_alert_url, data_url, self.alert_rules)

        # 4. Process each rule's response
        now = time.time()
        timestamp = get_current_time_str()

        for i, response_text in enumerate(alert_responses):
            if i >= len(self.alert_rules):
                break

            rule = self.alert_rules[i]
            answer = response_text.strip().lower()
            triggered = answer in ("yes", "true", "1")

            if not triggered:
                continue

            # Cooldown check
            last_trigger = self.alert_cooldowns.get(rule, 0)
            if now - last_trigger < self.cooldown_seconds:
                continue

            self.alert_cooldowns[rule] = now

            # Save evidence image
            safe_rule = rule[:40].replace("/", "_").replace("\\", "_").replace(" ", "_")
            img_filename = f"{self.current_run_id}_{int(now)}_{safe_rule}.jpg"
            img_path = os.path.join(evidence_dir, img_filename)
            try:
                with open(img_path, "wb") as f:
                    f.write(jpeg_bytes)
            except Exception as e:
                logger.error(f"Failed to save evidence image: {e}")
                img_path = ""

            # Relative path for DB
            rel_img_path = os.path.relpath(img_path, ROBOT_DATA_DIR) if img_path else ""

            # Save to DB
            try:
                with db_context() as (conn, cursor):
                    cursor.execute('''
                        INSERT INTO live_alerts (run_id, rule, response, image_path, timestamp, robot_id)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (self.current_run_id, rule, response_text.strip(), rel_img_path, timestamp, ROBOT_ID))
            except Exception as e:
                logger.error(f"Failed to save live alert to DB: {e}")

            alert_entry = {
                "rule": rule,
                "response": response_text.strip(),
                "image_path": rel_img_path,
                "timestamp": timestamp,
            }

            with self._lock:
                self.alerts.append(alert_entry)

            logger.warning(f"ALERT triggered: rule='{rule}' response='{response_text.strip()}'")

            # Send to Telegram
            if self.telegram_config and img_path:
                self._send_telegram_alert(rule, timestamp, jpeg_bytes)

    def _send_telegram_alert(self, rule, timestamp, jpeg_bytes):
        """Send alert photo + caption to Telegram."""
        bot_token = self.telegram_config.get("bot_token")
        user_id = self.telegram_config.get("user_id")
        if not bot_token or not user_id:
            return

        try:
            caption = f"⚠️ Live Monitor Alert\n\nRule: {rule}\nRobot: {ROBOT_ID}\nTime: {timestamp}"
            url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
            files = {"photo": (f"alert_{int(time.time())}.jpg", jpeg_bytes, "image/jpeg")}
            data = {"chat_id": user_id, "caption": caption}
            resp = requests.post(url, data=data, files=files, timeout=10)
            if resp.ok:
                logger.info(f"Telegram alert sent for rule: {rule}")
            else:
                logger.error(f"Telegram alert error: {resp.text}")
        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")


live_monitor = LiveMonitor()


class TestLiveMonitor:
    """Lightweight test monitor for settings page - no DB writes, keeps results in memory."""

    MAX_RESULTS = 50

    def __init__(self):
        self.is_running = False
        self._thread = None
        self._lock = threading.Lock()
        self.results = []
        self.error = None
        self.check_count = 0

    def start(self, vila_alert_url, rules, frame_func, interval=5.0):
        if self.is_running:
            return
        self.vila_alert_url = vila_alert_url.rstrip("/")
        self.rules = list(rules)
        self.frame_func = frame_func
        self.interval = interval
        self.results = []
        self.error = None
        self.check_count = 0
        self.is_running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info(f"TestLiveMonitor started: url={self.vila_alert_url}, rules={len(self.rules)}, interval={interval}s")

    def stop(self):
        if not self.is_running:
            return
        self.is_running = False
        if self._thread:
            self._thread.join(timeout=10)
            self._thread = None
        logger.info(f"TestLiveMonitor stopped after {self.check_count} checks")

    def get_status(self):
        with self._lock:
            return {
                "active": self.is_running,
                "check_count": self.check_count,
                "error": self.error,
                "results": list(self.results),
            }

    def _loop(self):
        while self.is_running:
            start = time.time()
            try:
                self._check_once()
            except Exception as e:
                logger.error(f"TestLiveMonitor error: {e}")
                with self._lock:
                    self.error = str(e)
            elapsed = time.time() - start
            sleep_time = max(0, self.interval - elapsed)
            end_sleep = time.time() + sleep_time
            while time.time() < end_sleep and self.is_running:
                time.sleep(0.5)

    def _check_once(self):
        img_response = self.frame_func()
        if not img_response or not img_response.data:
            with self._lock:
                self.error = "Camera not available"
            return

        b64 = base64.b64encode(img_response.data).decode()
        data_url = f"data:image/jpeg;base64,{b64}"

        alert_responses = _call_vila_chat(self.vila_alert_url, data_url, self.rules)

        timestamp = get_current_time_str()
        self.check_count += 1

        entry = {
            "check_id": self.check_count,
            "timestamp": timestamp,
            "responses": [],
        }
        for i, response_text in enumerate(alert_responses):
            if i >= len(self.rules):
                break
            entry["responses"].append({
                "rule": self.rules[i],
                "answer": response_text.strip(),
            })

        with self._lock:
            self.error = None
            self.results.append(entry)
            if len(self.results) > self.MAX_RESULTS:
                self.results = self.results[-self.MAX_RESULTS:]


test_live_monitor = TestLiveMonitor()

"""
Live Monitor - Background camera monitoring via VILA JPS Alert API during patrol.

Uses VILA JPS Stream API + Alert API + WebSocket for efficient continuous monitoring.
The legacy chat-completions approach is retained for TestLiveMonitor (settings page quick test).
"""

import base64
import json
import os
import threading
import time
from urllib.parse import urlparse

import cv2
import requests
import websocket

from config import ROBOT_ID, ROBOT_DATA_DIR
from database import db_context
from logger import get_logger
from utils import get_current_time_str

logger = get_logger("live_monitor", "live_monitor.log")

_VALID_RESPONSES = {"yes", "no", "0", "1", "true", "false"}

ALERT_SYSTEM_PROMPT = (
    "You are an AI assistant whose job is to evaluate a yes/no question on an image. "
    "Your response must be accurate and based on the image and MUST be 'yes' or 'no'. "
    "Do not respond with any numbers."
)

MAX_RULES = 10
WS_PORT = 5016
WS_RECONNECT_DELAY = 5
WS_MAX_RECONNECTS = 10


def _call_vila_chat(vila_url, data_url, rules, timeout=30, max_retries=1):
    """Call VILA chat completions once per rule (OpenAI-compatible).

    Uses NVIDIA-recommended settings: max_tokens=1, min_tokens=1, system prompt,
    and retry logic for non-boolean responses.
    Returns list of answer strings, one per rule.
    """
    url = f"{vila_url}/v1/chat/completions"
    answers = []

    for rule in rules:
        answer = ""
        for attempt in range(max_retries + 1):
            messages = [
                {"role": "system", "content": ALERT_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_url}},
                        {"type": "text", "text": rule},
                    ],
                },
            ]
            body = {
                "messages": messages,
                "max_tokens": 1,
                "min_tokens": 1,
            }

            try:
                resp = requests.post(url, json=body, timeout=timeout)
                resp.raise_for_status()
                data = resp.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                answer = content.strip().rstrip(".").strip()

                if answer.lower() in _VALID_RESPONSES:
                    break
                logger.warning(f"VILA non-boolean response '{answer}' for rule '{rule}', retry {attempt + 1}")
            except Exception as e:
                logger.error(f"VILA chat error for rule '{rule}': {e}")
                answer = ""
                break

        answers.append(answer)

    return answers


class LiveMonitor:
    """Background monitor using VILA JPS API: stream registration, alert rules, WebSocket events."""

    def __init__(self):
        self.is_monitoring = False
        self.current_run_id = None
        self.alerts = []
        self.alert_cooldowns = {}  # {rule_string: last_trigger_timestamp}
        self.cooldown_seconds = 60
        self._lock = threading.Lock()

        # JPS state
        self._stream_ids = []  # list of (stream_id, stream_config)
        self._ws_thread = None
        self._ws = None
        self._ws_stop = threading.Event()
        self._config = None

    def start(self, run_id, config):
        """Start live monitoring with VILA JPS API.

        Args:
            run_id: Current patrol run ID.
            config: dict with keys:
                vila_jps_url: str - VILA JPS base URL (e.g. "http://localhost:5010")
                streams: list of dicts, each with:
                    rtsp_url: str - full RTSP URL for VILA to pull
                    name: str - human-readable name
                    type: str - "robot_camera" or "external_rtsp"
                    evidence_func: callable (optional) - returns gRPC image for evidence capture
                rules: list of str - alert rule strings
                telegram_config: dict or None - {bot_token, user_id}
                mediamtx_external: str - mediamtx host:port for evidence capture
        """
        if self.is_monitoring:
            return

        self.current_run_id = run_id
        self._config = config
        self.alerts = []
        self.alert_cooldowns = {}
        self._stream_ids = []
        self._ws_stop.clear()

        vila_jps_url = config["vila_jps_url"].rstrip("/")
        streams = config.get("streams", [])
        rules = config.get("rules", [])

        if not streams or not rules:
            logger.warning("LiveMonitor: no streams or no rules, skipping")
            return

        # Truncate rules to max
        if len(rules) > MAX_RULES:
            logger.warning(f"Truncating rules from {len(rules)} to {MAX_RULES}")
            rules = rules[:MAX_RULES]

        # 1. Register each stream
        for stream in streams:
            try:
                stream_id = self._register_stream(vila_jps_url, stream["rtsp_url"], stream["name"])
                if stream_id:
                    self._stream_ids.append((stream_id, stream))
                    logger.info(f"Registered stream: {stream['name']} -> stream_id={stream_id}")
                else:
                    logger.error(f"Failed to register stream: {stream['name']}")
            except Exception as e:
                logger.error(f"Error registering stream {stream['name']}: {e}")

        if not self._stream_ids:
            logger.error("No streams registered, aborting LiveMonitor start")
            return

        # 2. Set alert rules per stream
        for stream_id, stream in self._stream_ids:
            try:
                self._set_alert_rules(vila_jps_url, stream_id, rules)
                logger.info(f"Set {len(rules)} alert rules for stream {stream_id}")
            except Exception as e:
                logger.error(f"Error setting alert rules for stream {stream_id}: {e}")

        # 3. Start WebSocket listener
        self.is_monitoring = True
        self._ws_thread = threading.Thread(target=self._ws_listener, daemon=True)
        self._ws_thread.start()

        logger.info(f"LiveMonitor started for run {run_id}: {len(self._stream_ids)} streams, {len(rules)} rules")

    def stop(self):
        """Stop monitoring: close WebSocket, deregister streams."""
        if not self.is_monitoring:
            return

        self.is_monitoring = False
        self._ws_stop.set()

        # Close WebSocket
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
            self._ws = None

        if self._ws_thread:
            self._ws_thread.join(timeout=10)
            self._ws_thread = None

        # Deregister streams
        if self._config:
            vila_jps_url = self._config["vila_jps_url"].rstrip("/")
            for stream_id, _ in self._stream_ids:
                try:
                    self._deregister_stream(vila_jps_url, stream_id)
                    logger.info(f"Deregistered stream: {stream_id}")
                except Exception as e:
                    logger.warning(f"Error deregistering stream {stream_id}: {e}")

        self._stream_ids = []
        logger.info(f"LiveMonitor stopped. Total alerts: {len(self.alerts)}")

    def get_alerts(self):
        """Return list of alerts collected during this run."""
        with self._lock:
            return list(self.alerts)

    # --- VILA JPS API ---

    def _register_stream(self, vila_jps_url, rtsp_url, name):
        """POST /api/v1/live-stream to register a stream. Returns stream_id or None."""
        url = f"{vila_jps_url}/api/v1/live-stream"
        body = {"url": rtsp_url, "name": name}
        resp = requests.post(url, json=body, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("id") or data.get("stream_id")

    def _set_alert_rules(self, vila_jps_url, stream_id, rules):
        """POST /api/v1/alerts to set alert rules for a stream."""
        url = f"{vila_jps_url}/api/v1/alerts"
        body = {"alerts": rules, "id": stream_id}
        resp = requests.post(url, json=body, timeout=15)
        resp.raise_for_status()

    def _deregister_stream(self, vila_jps_url, stream_id):
        """DELETE /api/v1/live-stream/{stream_id}."""
        url = f"{vila_jps_url}/api/v1/live-stream/{stream_id}"
        resp = requests.delete(url, timeout=10)
        resp.raise_for_status()

    # --- WebSocket Listener ---

    def _ws_listener(self):
        """Connect to VILA JPS WebSocket and listen for alert events."""
        vila_jps_url = self._config["vila_jps_url"].rstrip("/")
        parsed = urlparse(vila_jps_url)
        ws_host = parsed.hostname
        ws_url = f"ws://{ws_host}:{WS_PORT}/api/v1/alerts/ws"

        evidence_dir = os.path.join(ROBOT_DATA_DIR, "report", "live_alerts")
        os.makedirs(evidence_dir, exist_ok=True)

        reconnect_count = 0

        while not self._ws_stop.is_set() and reconnect_count < WS_MAX_RECONNECTS:
            try:
                logger.info(f"Connecting to VILA WS: {ws_url}")
                self._ws = websocket.WebSocket()
                self._ws.settimeout(5)
                self._ws.connect(ws_url)
                logger.info("VILA WebSocket connected")
                reconnect_count = 0  # Reset on successful connect

                while not self._ws_stop.is_set():
                    try:
                        raw = self._ws.recv()
                        if not raw:
                            continue
                        self._handle_ws_event(raw, evidence_dir)
                    except websocket.WebSocketTimeoutException:
                        continue
                    except websocket.WebSocketConnectionClosedException:
                        logger.warning("VILA WebSocket closed by server")
                        break

            except Exception as e:
                if self._ws_stop.is_set():
                    break
                reconnect_count += 1
                logger.warning(f"VILA WS error (attempt {reconnect_count}/{WS_MAX_RECONNECTS}): {e}")
                self._ws_stop.wait(WS_RECONNECT_DELAY)

        if reconnect_count >= WS_MAX_RECONNECTS:
            logger.error("VILA WebSocket max reconnects exceeded")

    def _handle_ws_event(self, raw, evidence_dir):
        """Process a single WebSocket alert event."""
        try:
            event = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            logger.debug(f"Non-JSON WS message: {raw[:200]}")
            return

        rule_string = event.get("rule_string") or event.get("alert") or event.get("rule", "")
        stream_id = event.get("stream_id") or event.get("id", "")
        alert_id = event.get("alert_id", "")

        if not rule_string:
            return

        # Find the stream config for this stream_id
        stream_config = None
        for sid, sc in self._stream_ids:
            if sid == stream_id:
                stream_config = sc
                break

        stream_type = stream_config.get("type", "unknown") if stream_config else "unknown"
        stream_name = stream_config.get("name", "Unknown") if stream_config else "Unknown"

        # Cooldown check (defense-in-depth; VILA also has 60s cooldown)
        now = time.time()
        cooldown_key = f"{stream_id}:{rule_string}"
        last_trigger = self.alert_cooldowns.get(cooldown_key, 0)
        if now - last_trigger < self.cooldown_seconds:
            return
        self.alert_cooldowns[cooldown_key] = now

        timestamp = get_current_time_str()
        logger.warning(f"ALERT: stream={stream_name} rule='{rule_string}' alert_id={alert_id}")

        # Capture evidence frame
        jpeg_bytes = self._capture_evidence(stream_config)

        # Save evidence image
        img_path = ""
        rel_img_path = ""
        if jpeg_bytes:
            safe_rule = rule_string[:40].replace("/", "_").replace("\\", "_").replace(" ", "_")
            img_filename = f"{self.current_run_id}_{int(now)}_{safe_rule}.jpg"
            img_path = os.path.join(evidence_dir, img_filename)
            try:
                with open(img_path, "wb") as f:
                    f.write(jpeg_bytes)
                rel_img_path = os.path.relpath(img_path, ROBOT_DATA_DIR)
            except Exception as e:
                logger.error(f"Failed to save evidence image: {e}")
                img_path = ""

        # Save to DB
        try:
            with db_context() as (conn, cursor):
                cursor.execute('''
                    INSERT INTO live_alerts (run_id, rule, response, image_path, timestamp, robot_id, stream_source)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (self.current_run_id, rule_string, "triggered", rel_img_path,
                      timestamp, ROBOT_ID, stream_type))
        except Exception as e:
            logger.error(f"Failed to save live alert to DB: {e}")

        alert_entry = {
            "rule": rule_string,
            "response": "triggered",
            "image_path": rel_img_path,
            "timestamp": timestamp,
            "stream_source": stream_type,
            "stream_name": stream_name,
        }

        with self._lock:
            self.alerts.append(alert_entry)

        # Send to Telegram
        tg_config = self._config.get("telegram_config") if self._config else None
        if tg_config and jpeg_bytes:
            self._send_telegram_alert(rule_string, stream_name, timestamp, jpeg_bytes, tg_config)

    def _capture_evidence(self, stream_config):
        """Capture a JPEG evidence frame from the appropriate source."""
        if not stream_config:
            return None

        stream_type = stream_config.get("type", "")

        # Robot camera: use gRPC frame_func for best quality
        if stream_type == "robot_camera":
            evidence_func = stream_config.get("evidence_func")
            if evidence_func:
                try:
                    img = evidence_func()
                    if img and img.data:
                        return img.data
                except Exception as e:
                    logger.error(f"Evidence capture via gRPC failed: {e}")

        # External RTSP: capture from the relay RTSP URL
        if stream_type == "external_rtsp":
            mediamtx_ext = self._config.get("mediamtx_external", "localhost:8554") if self._config else None
            rtsp_url = stream_config.get("rtsp_url", "")
            if rtsp_url and mediamtx_ext:
                try:
                    cap = cv2.VideoCapture(rtsp_url)
                    ret, frame = cap.read()
                    cap.release()
                    if ret and frame is not None:
                        _, buf = cv2.imencode('.jpg', frame)
                        return buf.tobytes()
                except Exception as e:
                    logger.error(f"Evidence capture via RTSP failed: {e}")

        return None

    def _send_telegram_alert(self, rule, stream_name, timestamp, jpeg_bytes, tg_config):
        """Send alert photo + caption to Telegram."""
        bot_token = tg_config.get("bot_token")
        user_id = tg_config.get("user_id")
        if not bot_token or not user_id:
            return

        try:
            caption = (
                f"⚠️ Live Monitor Alert\n\n"
                f"Rule: {rule}\n"
                f"Source: {stream_name}\n"
                f"Robot: {ROBOT_ID}\n"
                f"Time: {timestamp}"
            )
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


# === Legacy Test Monitor (settings page quick test via chat completions) ===

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
            "image": data_url,
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

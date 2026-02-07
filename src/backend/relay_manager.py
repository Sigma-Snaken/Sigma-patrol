"""
Relay Manager - manages ffmpeg subprocesses pushing camera streams to mediamtx.

Supports two relay types:
1. Robot camera (gRPC JPEG frames → ffmpeg pipe → mediamtx RTSP)
2. External RTSP camera (ffmpeg relay copy → mediamtx RTSP)

When RELAY_SERVICE_URL is set, relays are delegated to the Jetson-side relay
service via RelayServiceClient. Otherwise, the local RelayManager is used.
"""

import atexit
import signal
import socket
import subprocess
import threading
import time
from urllib.parse import urlparse

import requests as http_requests

from config import RELAY_SERVICE_URL
from logger import get_logger

logger = get_logger("relay_manager", "relay_manager.log")

MAX_RETRIES = 3
MONITOR_INTERVAL = 10
FEEDER_INTERVAL = 0.2  # 5 fps


def wait_for_stream(rtsp_url, max_wait=20):
    """Poll an RTSP URL via lightweight DESCRIBE until the stream exists on mediamtx.

    Uses raw TCP socket (fast, non-blocking) instead of OpenCV (blocks for seconds on 404).
    Returns True if stream became available within max_wait seconds, False otherwise.
    """
    parsed = urlparse(rtsp_url)
    host = parsed.hostname
    port = parsed.port or 8554
    path = parsed.path or "/"

    deadline = time.time() + max_wait
    attempt = 0

    while time.time() < deadline:
        attempt += 1
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3)
            s.connect((host, port))
            describe = (
                f"DESCRIBE rtsp://{host}:{port}{path} RTSP/1.0\r\n"
                f"CSeq: 1\r\n"
                f"\r\n"
            )
            s.sendall(describe.encode())
            resp = s.recv(1024).decode(errors="ignore")
            s.close()

            if "RTSP/1.0 200" in resp:
                logger.info(f"Stream ready after {attempt} attempts ({time.time() - deadline + max_wait:.1f}s): {rtsp_url}")
                return True
            else:
                status = resp.split("\r\n")[0] if resp else "no response"
                logger.debug(f"Stream not ready (attempt {attempt}): {status}")
        except Exception as e:
            logger.debug(f"Stream check error (attempt {attempt}): {e}")
        time.sleep(1)

    logger.warning(f"Stream not ready after {max_wait}s ({attempt} attempts): {rtsp_url}")
    return False


# === Relay Service Client (HTTP client for Jetson-side relay service) ===


class RelayServiceClient:
    """HTTP client for the Jetson-side relay service REST API."""

    def __init__(self, base_url):
        self._base_url = base_url.rstrip("/")
        self._session = http_requests.Session()
        self._feeders = {}  # key -> FrameFeederThread
        self._lock = threading.Lock()

    def is_available(self):
        """Check if the relay service is reachable."""
        try:
            resp = self._session.get(f"{self._base_url}/health", timeout=3)
            return resp.status_code == 200
        except Exception:
            return False

    def start_relay(self, key, relay_type, source_url=None):
        """Start a relay on the service. Returns (rtsp_path, error)."""
        body = {"key": key, "type": relay_type}
        if source_url:
            body["source_url"] = source_url
        try:
            resp = self._session.post(
                f"{self._base_url}/relays", json=body, timeout=10)
            data = resp.json()
            if resp.status_code == 200:
                return data.get("rtsp_path"), None
            return None, data.get("error", f"HTTP {resp.status_code}")
        except Exception as e:
            return None, str(e)

    def feed_frame(self, key, jpeg_bytes):
        """POST a single JPEG frame to the relay service."""
        try:
            resp = self._session.post(
                f"{self._base_url}/relays/{key}/frame",
                data=jpeg_bytes,
                headers={"Content-Type": "application/octet-stream"},
                timeout=5,
            )
            return resp.status_code == 204
        except Exception:
            return False

    def stop_relay(self, key):
        """Stop a specific relay on the service."""
        try:
            self._session.delete(f"{self._base_url}/relays/{key}", timeout=5)
        except Exception as e:
            logger.warning(f"RelayServiceClient: stop_relay({key}) error: {e}")

    def wait_for_stream(self, key, timeout=15):
        """Blocking readiness check on the relay service (Jetson localhost)."""
        try:
            resp = self._session.get(
                f"{self._base_url}/relays/{key}/ready",
                params={"timeout": timeout},
                timeout=timeout + 5,
            )
            if resp.status_code == 200:
                return resp.json().get("ready", False)
            return False
        except Exception as e:
            logger.warning(f"RelayServiceClient: wait_for_stream({key}) error: {e}")
            return False

    def stop_all(self):
        """Stop all relays on the service and all local frame feeders."""
        self.stop_all_feeders()
        try:
            self._session.post(f"{self._base_url}/relays/stop_all", timeout=5)
        except Exception as e:
            logger.warning(f"RelayServiceClient: stop_all error: {e}")

    def start_frame_feeder(self, key, frame_func):
        """Start a FrameFeederThread that grabs gRPC frames and POSTs them."""
        with self._lock:
            if key in self._feeders:
                return
            feeder = FrameFeederThread(key, frame_func, self)
            feeder.start()
            self._feeders[key] = feeder
            logger.info(f"Started frame feeder for {key}")

    def stop_frame_feeder(self, key):
        """Stop a specific frame feeder thread."""
        with self._lock:
            feeder = self._feeders.pop(key, None)
        if feeder:
            feeder.stop()
            logger.info(f"Stopped frame feeder for {key}")

    def stop_all_feeders(self):
        """Stop all frame feeder threads."""
        with self._lock:
            feeders = list(self._feeders.values())
            self._feeders.clear()
        for feeder in feeders:
            feeder.stop()


class FrameFeederThread:
    """Grabs gRPC frames and POSTs them to the relay service at ~5fps."""

    def __init__(self, key, frame_func, client):
        self._key = key
        self._frame_func = frame_func
        self._client = client
        self._stop_event = threading.Event()
        self._thread = None

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)

    def _run(self):
        while not self._stop_event.is_set():
            try:
                img = self._frame_func()
                if img and img.data:
                    self._client.feed_frame(self._key, img.data)
            except Exception as e:
                logger.debug(f"FrameFeeder error for {self._key}: {e}")
            self._stop_event.wait(FEEDER_INTERVAL)


# === Local Relay Manager (fallback when relay service not available) ===


class _RelayEntry:
    __slots__ = ("key", "relay_type", "process", "feeder_thread", "stop_event",
                 "started_at", "restart_count", "frame_func")

    def __init__(self, key, relay_type, process, feeder_thread=None,
                 stop_event=None, frame_func=None):
        self.key = key
        self.relay_type = relay_type
        self.process = process
        self.feeder_thread = feeder_thread
        self.stop_event = stop_event or threading.Event()
        self.frame_func = frame_func
        self.started_at = time.time()
        self.restart_count = 0


class RelayManager:
    """Manages ffmpeg relay subprocesses pushing to mediamtx RTSP server."""

    def __init__(self):
        self._relays = {}  # key -> _RelayEntry
        self._lock = threading.Lock()
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        atexit.register(self.stop_all)

    def start_robot_camera_relay(self, robot_id, frame_func, mediamtx_internal):
        """Start ffmpeg relay for robot camera gRPC frames.

        Args:
            robot_id: Robot identifier for RTSP path.
            frame_func: Callable returning gRPC image response with .data (JPEG bytes).
            mediamtx_internal: mediamtx host:port for ffmpeg to push to.

        Returns:
            RTSP path string, e.g. "/{robot_id}/camera"
        """
        key = f"{robot_id}/camera"
        rtsp_path = f"/{key}"
        rtsp_url = f"rtsp://{mediamtx_internal}{rtsp_path}"

        with self._lock:
            if key in self._relays and self._relays[key].process.poll() is None:
                logger.info(f"Robot camera relay already running: {key}")
                return rtsp_path

        cmd = [
            "ffmpeg", "-y",
            "-f", "image2pipe",
            "-framerate", "5",
            "-i", "pipe:0",
            "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-tune", "zerolatency",
            "-profile:v", "baseline",
            "-level", "3.1",
            "-pix_fmt", "yuv420p",
            "-x264-params", "keyint=30:min-keyint=30:repeat-headers=1",
            "-bsf:v", "dump_extra",
            "-f", "rtsp",
            "-rtsp_transport", "tcp",
            rtsp_url,
        ]

        logger.info(f"Starting robot camera relay: {key} -> {rtsp_url}")
        proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            text=True, bufsize=1,
        )
        threading.Thread(target=self._stderr_reader, args=(proc, key), daemon=True).start()

        stop_event = threading.Event()
        feeder = threading.Thread(
            target=self._feeder_loop,
            args=(proc, frame_func, stop_event, key),
            daemon=True,
        )
        feeder.start()

        entry = _RelayEntry(key, "robot_camera", proc,
                            feeder_thread=feeder, stop_event=stop_event,
                            frame_func=frame_func)

        with self._lock:
            self._relays[key] = entry

        return rtsp_path

    def start_external_rtsp_relay(self, robot_id, source_url, mediamtx_internal):
        """Start ffmpeg relay copying an external RTSP stream to mediamtx.

        Args:
            robot_id: Robot identifier for RTSP path.
            source_url: Source RTSP URL (e.g. rtsp://admin:pass@192.168.50.45:554/live).
            mediamtx_internal: mediamtx host:port for ffmpeg to push to.

        Returns:
            RTSP path string, e.g. "/{robot_id}/external"
        """
        key = f"{robot_id}/external"
        rtsp_path = f"/{key}"
        rtsp_url = f"rtsp://{mediamtx_internal}{rtsp_path}"

        with self._lock:
            if key in self._relays and self._relays[key].process.poll() is None:
                logger.info(f"External RTSP relay already running: {key}")
                return rtsp_path

        cmd = [
            "ffmpeg", "-y",
            "-rtsp_transport", "tcp",
            "-i", source_url,
            "-c:v", "copy",
            "-an",
            "-f", "rtsp",
            "-rtsp_transport", "tcp",
            rtsp_url,
        ]

        logger.info(f"Starting external RTSP relay: {key} -> {rtsp_url}")
        proc = subprocess.Popen(
            cmd, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            text=True, bufsize=1,
        )
        threading.Thread(target=self._stderr_reader, args=(proc, key), daemon=True).start()

        entry = _RelayEntry(key, "external_rtsp", proc)

        with self._lock:
            self._relays[key] = entry

        return rtsp_path

    def stop_relay(self, key):
        """Stop a specific relay by key."""
        with self._lock:
            entry = self._relays.pop(key, None)
        if not entry:
            return

        logger.info(f"Stopping relay: {key}")
        if entry.stop_event:
            entry.stop_event.set()

        self._terminate_process(entry.process)

        if entry.feeder_thread and entry.feeder_thread.is_alive():
            entry.feeder_thread.join(timeout=3)

    def stop_all(self):
        """Stop all active relays."""
        with self._lock:
            keys = list(self._relays.keys())
        for key in keys:
            self.stop_relay(key)

    def get_status(self):
        """Return status dict for all relays."""
        result = {}
        with self._lock:
            for key, entry in self._relays.items():
                running = entry.process.poll() is None
                uptime = time.time() - entry.started_at if running else 0
                result[key] = {
                    "type": entry.relay_type,
                    "running": running,
                    "uptime": round(uptime, 1),
                    "restart_count": entry.restart_count,
                }
        return result

    # --- Internal ---

    @staticmethod
    def _stderr_reader(proc, key):
        """Read ffmpeg stderr and log it."""
        try:
            for line in proc.stderr:
                line = line.strip()
                if line:
                    logger.info(f"ffmpeg[{key}]: {line}")
        except Exception:
            pass

    def _feeder_loop(self, proc, frame_func, stop_event, key):
        """Feed JPEG frames from gRPC to ffmpeg stdin."""
        while not stop_event.is_set():
            try:
                if proc.poll() is not None:
                    break
                img = frame_func()
                if img and img.data:
                    proc.stdin.write(img.data)
                    proc.stdin.flush()
            except (BrokenPipeError, OSError):
                break
            except Exception as e:
                logger.debug(f"Feeder error for {key}: {e}")

            stop_event.wait(FEEDER_INTERVAL)

        # Close stdin to signal ffmpeg
        try:
            proc.stdin.close()
        except Exception:
            pass

    def _terminate_process(self, proc):
        """SIGTERM → 5s wait → SIGKILL."""
        if proc.poll() is not None:
            return
        try:
            proc.send_signal(signal.SIGTERM)
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    def _monitor_loop(self):
        """Background thread: check relay health, restart dead processes."""
        while True:
            time.sleep(MONITOR_INTERVAL)
            with self._lock:
                entries = list(self._relays.values())

            for entry in entries:
                if entry.process.poll() is None:
                    continue  # still running

                if entry.restart_count >= MAX_RETRIES:
                    logger.error(f"Relay {entry.key} exceeded max retries ({MAX_RETRIES}), giving up")
                    continue

                delay = min(2 ** entry.restart_count, 30)
                logger.warning(f"Relay {entry.key} died, restarting in {delay}s (attempt {entry.restart_count + 1})")
                time.sleep(delay)

                # Restart
                try:
                    if entry.relay_type == "robot_camera" and entry.frame_func:
                        old_cmd = entry.process.args
                        new_proc = subprocess.Popen(
                            old_cmd, stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                            text=True, bufsize=1,
                        )
                        threading.Thread(target=self._stderr_reader, args=(new_proc, entry.key), daemon=True).start()
                        stop_event = threading.Event()
                        feeder = threading.Thread(
                            target=self._feeder_loop,
                            args=(new_proc, entry.frame_func, stop_event, entry.key),
                            daemon=True,
                        )
                        feeder.start()

                        with self._lock:
                            entry.process = new_proc
                            entry.stop_event = stop_event
                            entry.feeder_thread = feeder
                            entry.restart_count += 1
                            entry.started_at = time.time()
                    else:
                        old_cmd = entry.process.args
                        new_proc = subprocess.Popen(
                            old_cmd, stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                            text=True, bufsize=1,
                        )
                        threading.Thread(target=self._stderr_reader, args=(new_proc, entry.key), daemon=True).start()
                        with self._lock:
                            entry.process = new_proc
                            entry.restart_count += 1
                            entry.started_at = time.time()

                    logger.info(f"Relay {entry.key} restarted successfully")
                except Exception as e:
                    logger.error(f"Failed to restart relay {entry.key}: {e}")


# === Module-level instances ===

relay_manager = RelayManager()

# Relay service client (used when RELAY_SERVICE_URL is configured)
relay_service_client = RelayServiceClient(RELAY_SERVICE_URL) if RELAY_SERVICE_URL else None

if relay_service_client:
    logger.info(f"Relay service client configured: {RELAY_SERVICE_URL}")

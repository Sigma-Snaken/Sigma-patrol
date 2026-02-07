"""
Relay Manager - manages ffmpeg subprocesses pushing camera streams to mediamtx.

Supports two relay types:
1. Robot camera (gRPC JPEG frames → ffmpeg pipe → mediamtx RTSP)
2. External RTSP camera (ffmpeg relay copy → mediamtx RTSP)
"""

import atexit
import signal
import subprocess
import threading
import time

from logger import get_logger

logger = get_logger("relay_manager", "relay_manager.log")

MAX_RETRIES = 3
MONITOR_INTERVAL = 10
FEEDER_INTERVAL = 0.2  # 5 fps


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
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-tune", "zerolatency",
            "-pix_fmt", "yuv420p",
            "-f", "rtsp",
            "-rtsp_transport", "tcp",
            rtsp_url,
        ]

        logger.info(f"Starting robot camera relay: {key} -> {rtsp_url}")
        proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

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
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

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
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        )
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
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        )
                        with self._lock:
                            entry.process = new_proc
                            entry.restart_count += 1
                            entry.started_at = time.time()

                    logger.info(f"Relay {entry.key} restarted successfully")
                except Exception as e:
                    logger.error(f"Failed to restart relay {entry.key}: {e}")


relay_manager = RelayManager()

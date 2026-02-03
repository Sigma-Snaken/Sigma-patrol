"""
Patrol Service - Autonomous patrol orchestration with scheduled execution.
"""

import threading
import queue
import time
import os
import uuid
import io
from datetime import datetime
from PIL import Image
import asyncio

from config import SETTINGS_FILE, DEFAULT_SETTINGS, IMAGES_DIR, POINTS_FILE, DATA_DIR, BEDS_FILE
import requests
from utils import load_json, save_json, get_current_time_str, get_filename_timestamp
from database import get_db_connection, db_context, update_run_tokens
from robot_service import robot_service
from ai_service import ai_service, parse_ai_response
from pdf_service import generate_patrol_report
from logger import get_logger
from video_recorder import VideoRecorder
from mqtt_service import BioSensorMQTTClient

logger = get_logger("patrol_service", "patrol_service.log")

SCHEDULE_FILE = os.path.join(DATA_DIR, "patrol_schedule.json")


class PatrolService:
    """Manages autonomous patrol missions with AI-powered inspection."""

    def __init__(self):
        self.is_patrolling = False
        self.patrol_status = "Idle"
        self.current_patrol_index = -1
        self.current_run_id = None

        # Thread safety
        self.patrol_lock = threading.Lock()
        self.state_lock = threading.Lock()
        self.schedule_lock = threading.Lock()
        self.patrol_thread = None

        # Async inspection queue
        self.inspection_queue = queue.Queue()
        threading.Thread(target=self._inspection_worker, daemon=True).start()

        # Scheduled patrols
        self.scheduled_patrols = []
        self._load_schedule()
        threading.Thread(target=self._schedule_checker, daemon=True).start()

        # MQTT Client
        self.mqtt_client = None


    # === Schedule Management ===

    def _load_schedule(self):
        with self.schedule_lock:
            self.scheduled_patrols = load_json(SCHEDULE_FILE, [])
        logger.info(f"Loaded {len(self.scheduled_patrols)} scheduled patrols")

    def _save_schedule(self):
        with self.schedule_lock:
            save_json(SCHEDULE_FILE, self.scheduled_patrols)

    def get_schedule(self):
        with self.schedule_lock:
            return list(self.scheduled_patrols)

    def add_schedule(self, time_str, days=None, enabled=True):
        """Add scheduled patrol. Days: 0=Monday to 6=Sunday."""
        item = {
            "id": str(uuid.uuid4())[:8],
            "time": time_str,
            "days": days or [0, 1, 2, 3, 4, 5, 6],
            "enabled": enabled
        }
        with self.schedule_lock:
            self.scheduled_patrols.append(item)
        self._save_schedule()
        logger.info(f"Added scheduled patrol at {time_str}")
        return item

    def update_schedule(self, schedule_id, time_str=None, days=None, enabled=None):
        with self.schedule_lock:
            for item in self.scheduled_patrols:
                if item.get("id") == schedule_id:
                    if time_str is not None:
                        item["time"] = time_str
                    if days is not None:
                        item["days"] = days
                    if enabled is not None:
                        item["enabled"] = enabled
                    break
        self._save_schedule()

    def delete_schedule(self, schedule_id):
        with self.schedule_lock:
            self.scheduled_patrols = [s for s in self.scheduled_patrols if s.get("id") != schedule_id]
        self._save_schedule()

    def _schedule_checker(self):
        """Background thread checking for scheduled patrols."""
        last_triggered = {}

        while True:
            try:
                settings = load_json(SETTINGS_FILE, DEFAULT_SETTINGS)
                tz_name = settings.get("timezone", "UTC")

                try:
                    from zoneinfo import ZoneInfo
                    now = datetime.now(ZoneInfo(tz_name))
                except Exception:
                    now = datetime.now()

                current_time_str = now.strftime("%H:%M")
                current_day = now.weekday()
                current_date = now.strftime("%Y-%m-%d")

                with self.schedule_lock:
                    schedules = list(self.scheduled_patrols)

                for schedule in schedules:
                    if not schedule.get("enabled", True):
                        continue

                    schedule_id = schedule.get("id", "")
                    schedule_time = schedule.get("time", "")
                    schedule_days = schedule.get("days", [0, 1, 2, 3, 4, 5, 6])

                    if current_day not in schedule_days:
                        continue

                    if schedule_time == current_time_str:
                        trigger_key = f"{schedule_id}_{current_date}"
                        if trigger_key in last_triggered:
                            continue

                        with self.patrol_lock:
                            if self.is_patrolling:
                                logger.info(f"Scheduled patrol {schedule_id} skipped - already patrolling")
                                continue

                        logger.info(f"Scheduled patrol triggered: {schedule_id} at {schedule_time}")
                        last_triggered[trigger_key] = True
                        self.start_patrol()

                # Cleanup old triggers
                last_triggered = {k: v for k, v in last_triggered.items() if k.endswith(current_date)}

            except Exception as e:
                logger.error(f"Schedule checker error: {e}")

            check_interval = settings.get("schedule_check_interval", 30)
            time.sleep(check_interval)

    # === Status Management ===

    def get_status(self):
        with self.state_lock:
            return {
                "is_patrolling": self.is_patrolling,
                "status": self.patrol_status,
                "current_index": self.current_patrol_index
            }

    def _set_status(self, status):
        with self.state_lock:
            self.patrol_status = status

    def _set_patrol_index(self, index):
        with self.state_lock:
            self.current_patrol_index = index

    # === Patrol Control ===

    def start_patrol(self):
        with self.patrol_lock:
            if self.is_patrolling:
                return False, "Already patrolling"
            if self.patrol_thread and self.patrol_thread.is_alive():
                self.patrol_thread.join(timeout=5)
            self.is_patrolling = True
            with self.state_lock:
                self.current_patrol_index = -1
                self.current_run_id = None

        logger.info("Starting patrol...")
        self.patrol_thread = threading.Thread(target=self._patrol_logic, daemon=True)
        self.patrol_thread.start()
        return True, "Started"

    def stop_patrol(self):
        with self.patrol_lock:
            was_patrolling = self.is_patrolling
            self.is_patrolling = False
            self._set_status("Stopping...")

        if was_patrolling:
            logger.info("Stop patrol requested.")
            robot_service.cancel_command()
            robot_service.return_home()
        return True

    # === Inspection Worker ===

    def _inspection_worker(self):
        """Background worker processing inspection queue."""
        while True:
            task = self.inspection_queue.get()
            try:
                run_id, point, image_path, user_prompt, sys_prompt, results_list, img_uuid = task
                point_name = point.get('name', 'Unknown')
                logger.info(f"Worker: Processing {point_name}")

                try:
                    image = Image.open(image_path)
                except Exception as e:
                    logger.error(f"Worker Image Load Error for {point_name}: {e}")
                    continue

                # AI Analysis
                try:
                    response_obj = ai_service.generate_inspection(image, user_prompt, sys_prompt)
                    parsed = parse_ai_response(response_obj)
                except Exception as e:
                    logger.error(f"Worker AI Error for {point_name}: {e}")
                    parsed = parse_ai_response(None)
                    parsed['result_text'] = f"AI Error: {e}"
                    parsed['description'] = str(e)

                # Rename image
                new_path = self._rename_image(image_path, point_name, parsed['is_ng'], img_uuid)

                # Save to DB
                self._save_inspection(
                    run_id, point, point_name, user_prompt,
                    parsed, new_path, "Success"
                )

                results_list.append({"point": point_name, "result": parsed['result_text']})
                logger.info(f"Worker: Finished {point_name}")

            except Exception as e:
                logger.critical(f"Worker Fatal Error: {e}")
            finally:
                self.inspection_queue.task_done()

    def _rename_image(self, image_path, point_name, is_ng, img_uuid):
        """Rename image with point name and status."""
        try:
            safe_name = point_name.replace("/", "_").replace("\\", "_")
            status_tag = "NG" if is_ng else "OK"
            new_filename = f"{safe_name}_{status_tag}_{img_uuid}.jpg"
            new_path = os.path.join(os.path.dirname(image_path), new_filename)
            os.rename(image_path, new_path)
            return new_path
        except OSError as e:
            logger.warning(f"Failed to rename image: {e}")
            return image_path

    def _save_inspection(self, run_id, point, point_name, prompt, parsed, image_path, move_status):
        """Save inspection result to database."""
        rel_path = image_path.replace(IMAGES_DIR + "/", "").lstrip('/') if image_path else ""

        try:
            with db_context() as (conn, cursor):
                cursor.execute('''
                    INSERT INTO inspection_results
                    (run_id, point_name, coordinate_x, coordinate_y, prompt, ai_response,
                     is_ng, ai_description, token_usage, prompt_tokens, candidate_tokens,
                     total_tokens, image_path, timestamp, robot_moving_status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    run_id, point_name, point.get('x'), point.get('y'), prompt,
                    parsed['result_text'], 1 if parsed['is_ng'] else 0, parsed['description'],
                    parsed['usage_json'], parsed['prompt_tokens'], parsed['candidate_tokens'],
                    parsed['total_tokens'], rel_path, get_current_time_str(), move_status
                ))
        except Exception as e:
            logger.error(f"DB Error saving inspection for {point_name}: {e}")

    # === Internal Helpers ===
    
    def _ensure_mqtt_client(self, settings):
        """Initialize or update MQTT client based on settings."""
        if settings.get("mqtt_enabled", False):
            broker = settings.get("mqtt_broker", "localhost")
            port = settings.get("mqtt_port", 1883)
            topic = settings.get("mqtt_topic", "")
            
            # If client exists but config changed, restart it (simplified: just keep existing for now or restart)
            # For robustness, we create if None.
            if self.mqtt_client is None:
                logger.info(f"Initializing MQTT Client: {broker}:{port}")
                self.mqtt_client = BioSensorMQTTClient(broker, port, topic)
                self.mqtt_client.start()
        else:
            if self.mqtt_client:
                self.mqtt_client.stop()
                self.mqtt_client = None

    # === Main Patrol Logic ===

    def _patrol_logic(self):
        self._set_status("Starting...")
        points = load_json(POINTS_FILE, [])
        settings = load_json(SETTINGS_FILE, DEFAULT_SETTINGS)

        # Validate AI config
        if not ai_service.is_configured():
            self._set_status("Error: AI Not Configured")
            logger.error("Patrol started but AI not configured.")
            with self.patrol_lock:
                self.is_patrolling = False
            return

        model_name = ai_service.get_model_name()
        to_patrol = [p for p in points if p.get('enabled', True)]

        if not to_patrol:
            self._set_status("No enabled points")
            with self.patrol_lock:
                self.is_patrolling = False
            return

        # Create patrol run record
        try:
            with db_context() as (conn, cursor):
                cursor.execute(
                    'INSERT INTO patrol_runs (start_time, status, robot_serial, model_id) VALUES (?, ?, ?, ?)',
                    (get_current_time_str(), "Running", robot_service.get_serial(), model_name)
                )
                with self.state_lock:
                    self.current_run_id = cursor.lastrowid
        except Exception as e:
            logger.error(f"Failed to create patrol run: {e}")
            self._set_status("Error: Database Error")
            with self.patrol_lock:
                self.is_patrolling = False
            return

        logger.info(f"Patrol Run {self.current_run_id} started with {len(to_patrol)} points.")

        # Create run folder
        run_folder = f"{self.current_run_id}_{get_filename_timestamp()}"
        run_images_dir = os.path.join(IMAGES_DIR, run_folder)
        os.makedirs(run_images_dir, exist_ok=True)
        
        # Video recording setup
        recorder = None
        video_filename = None
        if settings.get("enable_video_recording", False):
            video_dir = os.path.join(DATA_DIR, "report", "video")
            os.makedirs(video_dir, exist_ok=True)
            video_filename = os.path.join(video_dir, f"{self.current_run_id}_{get_filename_timestamp()}.mp4") # Use mp4 as tested
            
            self._set_status("Starting Video Recording...")
            recorder = VideoRecorder(video_filename, robot_service.get_front_camera_image)
            recorder.start()

        inspections_data = []
        turbo_mode = settings.get('turbo_mode', False)
        patrol_mode = settings.get('patrol_mode', 'visual')

        # Ensure MQTT if needed
        if patrol_mode == 'physiological':
             self._ensure_mqtt_client(settings)
             if not self.mqtt_client:
                 logger.warning("Physiological mode selected but MQTT not enabled/initialized.")

        # Main patrol loop
        for i, point in enumerate(to_patrol):
            with self.patrol_lock:
                if not self.is_patrolling:
                    break

            self._set_patrol_index(i)
            point_name = point.get('name', 'Unknown')
            self._set_status(f"Moving to {point_name}...")
            logger.info(f"Moving to {i+1}/{len(to_patrol)}: {point_name}")

            # Move to point
            move_status = self._move_to_point(point, settings)

            if move_status != "Success":
                self._save_inspection(
                    self.current_run_id, point, point_name, "",
                    {'result_text': "Move Failed", 'is_ng': True, 'description': move_status,
                     'prompt_tokens': 0, 'candidate_tokens': 0, 'total_tokens': 0, 'usage_json': '{}'},
                    "", move_status
                )
                time.sleep(1)
                continue

            with self.patrol_lock:
                if not self.is_patrolling:
                    break

            # Inspect point
            self._set_status(f"Inspecting {point_name}...")
            inspection_delay = settings.get('inspection_delay', 2)
            time.sleep(inspection_delay)

            if patrol_mode == 'physiological':
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self._inspect_point_physiological(
                    point, point_name, inspections_data, settings
                ))
                loop.close()
            else:
                self._inspect_point(
                    point, point_name, run_images_dir, settings,
                    turbo_mode, inspections_data
                )

        # Finalize patrol
        with self.patrol_lock:
            was_patrolling = self.is_patrolling
        final_status = "Completed" if was_patrolling else "Patrol Stopped"

        video_path = None
        video_analysis_text = None

        if recorder:
            recorder.stop()
            if was_patrolling:
                video_path = video_filename

        if was_patrolling:
            # In turbo mode, start returning home immediately while images are still processing
            self._set_status("Returning Home...")
            try:
                robot_service.return_home()
            except Exception as e:
                logger.error(f"Return home failed: {e}")

            # Wait for async inspections to complete (robot is moving home in parallel)
            if turbo_mode:
                self._set_status("Processing Images...")
                self.inspection_queue.join()

            time.sleep(2)

            if recorder:
                self._set_status("Analyzing Video...")
                try:
                    vid_prompt = settings.get("video_prompt", "Analyze this patrol video.")
                    analysis_result = ai_service.analyze_video(video_filename, vid_prompt)
                    video_analysis_text = analysis_result['result']
                except Exception as e:
                    logger.error(f"Video analysis failed: {e}")
                    video_analysis_text = f"Analysis Failed: {e}"

            self._set_status("Generating Report...")
            self._generate_report(inspections_data, settings, video_analysis_text)

            self._set_status("Finished")

        # Update run status and tokens
        try:
            update_run_tokens(self.current_run_id)
            with db_context() as (conn, cursor):
                cursor.execute(
                    'UPDATE patrol_runs SET end_time = ?, status = ?, video_path = ?, video_analysis = ? WHERE id = ?',
                    (get_current_time_str(), final_status, video_path, video_analysis_text, self.current_run_id)
                )
        except Exception as e:
            logger.error(f"DB Error updating patrol status: {e}")

        logger.info(f"Patrol Run {self.current_run_id} finished: {final_status}")
        with self.patrol_lock:
            self.is_patrolling = False
        # Reset current_run_id so results API returns empty until next patrol
        with self.state_lock:
            self.current_run_id = None

    def _move_to_point(self, point, settings):
        """Move robot to patrol point. Returns status string."""
        if not robot_service.get_client():
            return "Error: Disconnected"

        patrol_mode = settings.get("patrol_mode", "visual")
        shelf_id = settings.get("mqtt_shelf_id", "")

        try:
            if patrol_mode == "physiological" and shelf_id:
                # Use move_shelf for physiological mode if shelf_id is set
                # Get location_id from beds.json based on bed_key
                beds_config = load_json(BEDS_FILE, {})
                beds = beds_config.get('beds', {})

                # Get bed_key from point config (prefer bed_key, fallback to name)
                bed_key = point.get('bed_key', point.get('name', ''))

                # Look up location_id from beds config
                bed_info = beds.get(bed_key, {})
                location_id = bed_info.get('location_id')

                # Fallback to default format if not found
                if not location_id:
                    location_id = f"B_{bed_key}" if bed_key else ''

                if not location_id:
                    return "Error: No Location ID"

                logger.info(f"Moving Shelf {shelf_id} to {location_id} (bed: {bed_key})...")
                robot_service.move_shelf(shelf_id, location_id, wait=True)
                # Note: move_shelf return value checking might differ, we assume success or exception
                return "Success"
            else:
                # Standard move
                result = robot_service.move_to(
                    float(point['x']), float(point['y']),
                    float(point.get('theta', 0.0)), wait=True
                )
                if result and getattr(result, 'success', False):
                    return "Success"
                error_code = getattr(result, 'error_code', 'Unknown') if result else 'No Result'
                return f"Error: {error_code}"
        except Exception as e:
            return f"Error: {e}"

    def _inspect_point(self, point, point_name, run_images_dir, settings, turbo_mode, inspections_data):
        """Capture image and run AI inspection."""
        try:
            img_response = robot_service.get_front_camera_image()
            if not img_response:
                return

            image = Image.open(io.BytesIO(img_response.data))
            img_uuid = str(uuid.uuid4())
            safe_name = point_name.replace("/", "_").replace("\\", "_")
            img_path = os.path.join(run_images_dir, f"{safe_name}_processing_{img_uuid}.jpg")
            image.save(img_path)

            user_prompt = point.get('prompt', 'Is everything normal?')
            sys_prompt = settings.get('system_prompt', '')

            if turbo_mode:
                logger.info(f"Queuing inspection for {point_name}")
                self.inspection_queue.put((
                    self.current_run_id, point, img_path,
                    user_prompt, sys_prompt, inspections_data, img_uuid
                ))
            else:
                logger.info(f"Analyzing {point_name}")
                response_obj = ai_service.generate_inspection(image, user_prompt, sys_prompt)
                parsed = parse_ai_response(response_obj)

                new_path = self._rename_image(img_path, point_name, parsed['is_ng'], img_uuid)
                self._save_inspection(
                    self.current_run_id, point, point_name, user_prompt,
                    parsed, new_path, "Success"
                )
                inspections_data.append({"point": point_name, "result": parsed['result_text']})

        except Exception as e:
            logger.error(f"Inspection Error at {point_name}: {e}")
            self._set_status(f"Error at {point_name}")
            time.sleep(2)

    def _generate_report(self, inspections_data, settings, video_analysis_text=None):
        """Generate AI summary report."""
        if not inspections_data:
            return

        try:
            custom_prompt = settings.get('report_prompt', '').strip()
            if custom_prompt:
                report_prompt = f"{custom_prompt}\n\n"
            else:
                report_prompt = "Generate a summary report for this patrol:\n\n"

            for item in inspections_data:
                report_prompt += f"- Point: {item['point']}\n  Result: {item['result']}\n\n"

            if video_analysis_text:
                report_prompt += f"\n\nVideo Analysis Summary:\n{video_analysis_text}\n\n"

            if not custom_prompt:
                report_prompt += "Provide a concise overview of status and anomalies."

            response_obj = ai_service.generate_report(report_prompt)
            parsed = parse_ai_response(response_obj)

            with db_context() as (conn, cursor):
                cursor.execute(
                    'UPDATE patrol_runs SET report_content = ?, token_usage = ? WHERE id = ?',
                    (parsed['result_text'], parsed['usage_json'], self.current_run_id)
                )

            logger.info("Report generated and saved.")

            # --- Telegram Notification ---
            if settings.get('enable_telegram', False):
                self._send_telegram_notification(settings, parsed['result_text'])

        except Exception as e:
            logger.error(f"Report Generation Error: {e}")

    def _send_telegram_notification(self, settings, report_text):
        """Send patrol report and PDF to Telegram."""
        bot_token = settings.get('telegram_bot_token')
        user_id = settings.get('telegram_user_id')

        if not bot_token or not user_id:
            logger.warning("Telegram enabled but token or user_id missing.")
            return

        try:
            logger.info("Sending Telegram notification...")

            # 1. Send Text Message
            text_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            text_payload = {
                "chat_id": user_id,
                "text": f"🤖 *Patrol Completed*\n\n{report_text[:1000]}...", # Truncate if too long
                "parse_mode": "Markdown"
            }
            resp = requests.post(text_url, json=text_payload, timeout=10)
            if not resp.ok:
                logger.error(f"Telegram Text Error: {resp.text}")

            # 2. Send PDF Document with start_time in filename
            try:
                pdf_bytes = generate_patrol_report(self.current_run_id)

                # Get start_time from database for filename
                pdf_filename = f'Patrol_Report_{self.current_run_id}.pdf'  # Default fallback
                try:
                    with db_context() as (conn, cursor):
                        cursor.execute('SELECT start_time FROM patrol_runs WHERE id = ?', (self.current_run_id,))
                        row = cursor.fetchone()
                        if row and row['start_time']:
                            # Convert "YYYY-MM-DD HH:MM:SS" to "YYYY-MM-DD_HHMMSS"
                            start_time_str = row['start_time']
                            filename_ts = start_time_str.replace(" ", "_").replace(":", "")
                            pdf_filename = f'Patrol_Report_{filename_ts}.pdf'
                except Exception as e_db:
                    logger.warning(f"Could not get start_time for PDF filename: {e_db}")

                doc_url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
                files = {
                    'document': (
                        pdf_filename,
                        pdf_bytes,
                        'application/pdf'
                    )
                }
                data = {'chat_id': user_id}

                resp_doc = requests.post(doc_url, data=data, files=files, timeout=30)
                if resp_doc.ok:
                    logger.info("Telegram notification sent successfully.")
                else:
                    logger.error(f"Telegram PDF Error: {resp_doc.text}")

            except Exception as e_pdf:
                logger.error(f"Failed to generate/send PDF to Telegram: {e_pdf}")

        except Exception as e:
            logger.error(f"Telegram Notification Failed: {e}")


    async def _inspect_point_physiological(self, point, point_name, inspections_data, settings=None):
        """Run physiological inspection using MQTT."""
        if not self.mqtt_client:
            logger.error("MQTT Client not available for physiological inspection")
            inspections_data.append({"point": point_name, "result": "MQTT Error"})
            return

        if settings is None:
            settings = {}

        try:
            # We use the current run_id as the task context
            task_id = f"{self.current_run_id}"

            # Get bed_key from point config or use point_name
            target_bed = point.get('bed_key', point.get('bed_id', point_name))

            logger.info(f"Waiting for physiological data for {target_bed}...")
            self._set_status(f"Scanning {target_bed}...")

            result = await self.mqtt_client.get_valid_scan_data(task_id, target_bed, settings)
            
            d = result.get('data')
            if d:
                status_text = f"BPM: {d.get('bpm')}, RPM: {d.get('rpm')}"
                inspections_data.append({"point": point_name, "result": status_text})
                
                # Save to existing inspection_results for compatibility?
                # The MQTT client saves to its own DB. 
                # We might want to unify this, but for now we follow the plan of minimal disruption.
                # However, for the report generation to work, we added the result to inspections_data.
            else:
                inspections_data.append({"point": point_name, "result": "No Data / Timeout"})

        except Exception as e:
            logger.error(f"Physiological Inspection Error: {e}")
            inspections_data.append({"point": point_name, "result": f"Error: {e}"})


patrol_service = PatrolService()

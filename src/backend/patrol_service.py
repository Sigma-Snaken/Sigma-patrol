import threading
import queue
import time
import os
import uuid
import io
from datetime import datetime
from PIL import Image
import json

from config import SETTINGS_FILE, DEFAULT_SETTINGS, IMAGES_DIR, POINTS_FILE
from utils import load_json
from database import get_db_connection
from robot_service import robot_service
from ai_service import ai_service
from logger import get_logger
from time_utils import get_current_time_str, get_current_filename_time_str

logger = get_logger("patrol_service", "patrol_service.log")

class PatrolService:
    def __init__(self):
        self.is_patrolling = False
        self.patrol_status = "Idle"
        self.current_patrol_index = -1
        self.current_run_id = None
        self.patrol_lock = threading.Lock()
        
        self.inspection_queue = queue.Queue()
        threading.Thread(target=self._inspection_worker, daemon=True).start()

    def get_status(self):
        return {
            "is_patrolling": self.is_patrolling,
            "status": self.patrol_status,
            "current_index": self.current_patrol_index
        }

    def start_patrol(self):
        with self.patrol_lock:
            if self.is_patrolling:
                logger.warning("Attempted to start patrol while already running.")
                return False, "Already patrolling"
            self.is_patrolling = True
        
        logger.info("Starting patrol...")
        threading.Thread(target=self._patrol_logic, daemon=True).start()
        return True, "Started"

    def stop_patrol(self):
        with self.patrol_lock:
            self.is_patrolling = False
            self.patrol_status = "Stopping..."
        
        logger.info("Stop patrol requested.")
        robot_service.cancel_command()
        logger.info("Command cancelled.")
        robot_service.return_home()
        logger.info("Returning home.")
        return True

    def _inspection_worker(self):
        while True:
            task = self.inspection_queue.get()
            try:
                # model argument is no longer needed/used
                run_id, point, image_path, user_prompt, sys_prompt, _, results_list, img_uuid = task
                
                point_name = point.get('name', 'Unknown')
                logger.info(f"Worker: Processing inspection for {point_name}")
                
                # Load Image
                try:
                    image = Image.open(image_path)
                except Exception as e:
                    logger.error(f"Worker Image Load Error for {point_name}: {e}")
                    continue
                
                # Call Gemini via AI Service
                token_usage_str = "{}"
                ai_description = ""
                is_ng_val = 0
                prompt_tokens = 0
                candidate_tokens = 0
                total_tokens = 0
                
                try:
                    response_obj = ai_service.generate_inspection(image, user_prompt, sys_prompt)
                    # Handle new structure
                    if isinstance(response_obj, dict) and "result" in response_obj:
                        result_data = response_obj["result"]
                        usage_data = response_obj.get("usage", {})
                        token_usage_str = json.dumps(usage_data)
                        prompt_tokens = usage_data.get("prompt_token_count", 0)
                        candidate_tokens = usage_data.get("candidates_token_count", 0)
                        total_tokens = usage_data.get("total_token_count", 0)
                    else:
                         # Fallback if service reverted or error
                         result_data = response_obj
                         usage_data = {}

                    if isinstance(result_data, dict):
                        is_ng = result_data.get("is_NG", False)
                        is_ng_val = 1 if is_ng else 0
                        ai_description = result_data.get("Description", "")
                        safe_response = "NG" if is_ng else "OK"
                        result_text = json.dumps(result_data, ensure_ascii=False)
                    else:
                        result_text = str(result_data)
                        ai_description = result_text
                        safe_response = result_text[:5].replace("/", "_").replace("\\", "_").replace(":", "").replace("\n", "").strip()

                except Exception as e:
                    result_text = f"AI Error: {e}"
                    safe_response = "Error"
                    logger.error(f"Worker Gemini Error for {point_name}: {e}")
                    
                # Rename Image
                try:
                    safe_point_name = point_name.replace("/", "_").replace("\\", "_")
                    
                    new_filename = f"{safe_point_name}_{safe_response}_{img_uuid}.jpg"
                    new_full_path = os.path.join(os.path.dirname(image_path), new_filename)
                    
                    os.rename(image_path, new_full_path)
                    image_path = new_full_path
                    logger.info(f"Renamed image for {point_name} to {new_filename}")
                except Exception as e:
                    logger.error(f"Worker Rename Error for {point_name}: {e}")

                # Save Result to DB
                try:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute(
                        '''INSERT INTO inspection_results 
                           (run_id, point_name, coordinate_x, coordinate_y, prompt, ai_response, is_ng, ai_description, token_usage, prompt_tokens, candidate_tokens, total_tokens, image_path, timestamp, robot_moving_status) 
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                        (run_id, point_name, point.get('x'), point.get('y'), user_prompt, result_text, is_ng_val, ai_description, token_usage_str, prompt_tokens, candidate_tokens, total_tokens, image_path.replace(os.path.join(IMAGES_DIR, ""), "").lstrip('/'), get_current_time_str(), "Success")
                    )
                    conn.commit()
                    conn.close()
                except Exception as e:
                    logger.error(f"Worker DB Error for {point_name}: {e}")

                results_list.append({
                    "point": point_name,
                    "result": result_text
                })
                
                logger.info(f"Worker: Finished processing {point_name}")
                
            except Exception as e:
                logger.critical(f"Worker Fatal Error: {e}")
            finally:
                self.inspection_queue.task_done()

    def _patrol_logic(self):
        self.patrol_status = "Starting..."
        points = load_json(POINTS_FILE, [])
        settings = load_json(SETTINGS_FILE, DEFAULT_SETTINGS)
        
        # Check AI config
        if not ai_service.is_configured():
             self.patrol_status = "Error: AI Not Configured (API Key?)"
             logger.error("Patrol started but AI not configured.")
             self.is_patrolling = False
             return
        
        model_name = ai_service.get_model_name()
        logger.info(f"Patrol using model: {model_name}")

        to_patrol = [p for p in points if p.get('enabled', True)]
        
        if not to_patrol:
            self.patrol_status = "No enabled points"
            logger.warning("Patrol started but no points enabled.")
            self.is_patrolling = False
            return

        # Start DB Record
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            'INSERT INTO patrol_runs (start_time, status, robot_serial, model_id) VALUES (?, ?, ?, ?)',
            (get_current_time_str(), "Running", robot_service.get_serial(), model_name)
        )
        self.current_run_id = cursor.lastrowid
        conn.commit()
        conn.close()
        logger.info(f"Patrol Run ID: {self.current_run_id} started with {len(to_patrol)} points.")
        
        # Create Run Folder
        start_time_str = get_current_filename_time_str()
        run_folder_name = f"{self.current_run_id}_{start_time_str}"
        run_images_dir = os.path.join(IMAGES_DIR, run_folder_name)
        os.makedirs(run_images_dir, exist_ok=True)

        inspections_data = []

        for i, point in enumerate(to_patrol):
            if not self.is_patrolling:
                break
                
            self.current_patrol_index = i
            point_name = point.get('name', 'Unknown')
            self.patrol_status = f"Moving to {point_name}..."
            logger.info(f"Moving to point {i+1}/{len(to_patrol)}: {point_name}")
            
            # Move
            move_status = "Unknown"
            if robot_service.get_client():
                try:
                    target_x = float(point['x'])
                    target_y = float(point['y'])
                    target_theta = float(point.get('theta', 0.0))
                    
                    # Blocking call, returns Result object
                    result = robot_service.move_to(target_x, target_y, target_theta, wait=True)
                    
                    if result:
                        if getattr(result, 'success', False):
                            move_status = "Success"
                            logger.info(f"Move to {point_name} successful.")
                        else:
                            # Try to get error code
                            error_code = getattr(result, 'error_code', 'Unknown')
                            move_status = f"Error: {error_code}"
                            self.patrol_status = f"Move Failed: {move_status}"
                            logger.warning(f"Move failed for {point_name}: {move_status}")
                    else:
                        move_status = "Error: No Result"
                        logger.error(f"No result from move_to for {point_name}")

                except Exception as e:
                    move_status = f"Error: {e}"
                    self.patrol_status = f"Move Error: {e}"
                    logger.error(f"Patrol Move Error for {point_name}: {e}")
            else:
                 move_status = "Error: Disconnected"
                 logger.error("Robot service not connected during patrol.")
            
            # Check move status
            if move_status != "Success":
                try:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute(
                        '''INSERT INTO inspection_results 
                           (run_id, point_name, coordinate_x, coordinate_y, prompt, ai_response, is_ng, ai_description, token_usage, prompt_tokens, candidate_tokens, total_tokens, image_path, timestamp, robot_moving_status) 
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                        (self.current_run_id, point_name, point.get('x'), point.get('y'), "", "Move Failed", 1, move_status, "{}", 0, 0, 0, "", get_current_time_str(), move_status)
                    )
                    conn.commit()
                    conn.close()
                except Exception as db_e:
                    logger.error(f"DB Error saving move failure for {point_name}: {db_e}")
                
                # Continue specific request: "Once ... receives error or success ... can execute next action"
                # If error, we logged it and saved to DB. User usually implies skipping inspection if move failed.
                time.sleep(1)
                continue
            
            if not self.is_patrolling: break

            # Inspect
            self.patrol_status = f"Inspecting {point_name}..."
            # logger.info(f"Inspecting {point_name}")
            time.sleep(2)
            
            try:
                img_response = robot_service.get_front_camera_image()
                if img_response:
                    image = Image.open(io.BytesIO(img_response.data))
                    
                    img_uuid = str(uuid.uuid4())
                    safe_point_name = point_name.replace("/", "_").replace("\\", "_")
                    
                    img_filename = f"{safe_point_name}_processing_{img_uuid}.jpg"
                    img_full_path = os.path.join(run_images_dir, img_filename)
                    image.save(img_full_path)
                    
                    user_prompt = point.get('prompt', 'Is everything normal?')
                    sys_prompt = settings.get('system_prompt', '')
                    turbo_mode = settings.get('turbo_mode', False)
                    
                    if turbo_mode:
                        logger.info(f"Queuing inspection for {point_name} (Turbo Mode)")
                        # We pass None for model, the worker uses global ai_service
                        self.inspection_queue.put((
                            self.current_run_id, point, img_full_path, user_prompt, sys_prompt, None, inspections_data, img_uuid
                        ))
                    else:
                        # Blocking mode
                        logger.info(f"Analyzing {point_name} (Blocking Mode)")
                        
                        token_usage_str = "{}"
                        ai_description = ""
                        is_ng_val = 0
                        prompt_tokens = 0
                        candidate_tokens = 0
                        total_tokens = 0
                        
                        response_obj = ai_service.generate_inspection(image, user_prompt, sys_prompt)
                        # Handle new structure
                        if isinstance(response_obj, dict) and "result" in response_obj:
                            result_data = response_obj["result"]
                            usage_data = response_obj.get("usage", {})
                            token_usage_str = json.dumps(usage_data)
                            prompt_tokens = usage_data.get("prompt_token_count", 0)
                            candidate_tokens = usage_data.get("candidates_token_count", 0)
                            total_tokens = usage_data.get("total_token_count", 0)
                        else:
                             result_data = response_obj
                        
                        if isinstance(result_data, dict):
                            is_ng = result_data.get("is_NG", False)
                            is_ng_val = 1 if is_ng else 0
                            ai_description = result_data.get("Description", "")
                            safe_response = "NG" if is_ng else "OK"
                            result_text = json.dumps(result_data, ensure_ascii=False)
                        else:
                            result_text = str(result_data)
                            ai_description = result_text
                            safe_response = result_text[:5].replace("/", "_").replace("\\", "").replace("\n", "").strip()

                        # Rename
                        try:
                            new_filename = f"{safe_point_name}_{safe_response}_{img_uuid}.jpg"
                            new_full_path = os.path.join(run_images_dir, new_filename)
                            os.rename(img_full_path, new_full_path)
                            img_full_path = new_full_path
                        except: pass
                        
                        img_path_rel = os.path.relpath(img_full_path, IMAGES_DIR)
                        
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute(
                        '''INSERT INTO inspection_results 
                           (run_id, point_name, coordinate_x, coordinate_y, prompt, ai_response, is_ng, ai_description, token_usage, prompt_tokens, candidate_tokens, total_tokens, image_path, timestamp, robot_moving_status) 
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                        (self.current_run_id, point_name, point.get('x'), point.get('y'), user_prompt, result_text, is_ng_val, ai_description, token_usage_str, prompt_tokens, candidate_tokens, total_tokens, img_path_rel, get_current_time_str(), "Success")
                        )
                        conn.commit()
                        conn.close()
                        
                        inspections_data.append({
                            "point": point_name,
                            "result": result_text
                        })

            except Exception as e:
                logger.error(f"Patrol Inspection Error at {point_name}: {e}")
                self.patrol_status = f"Error at {point_name}"
                time.sleep(2)

        # End
        final_status = "Patrol Stopped"
        if self.is_patrolling:
            final_status = "Completed"
            if settings.get('turbo_mode', False):
                self.patrol_status = "Processing Images..."
                logger.info("Waiting for inspection queue to finish...")
                self.inspection_queue.join()
                logger.info("Inspection queue finished.")
            
            self.patrol_status = "Patrol Complete. Generating Report..."
            logger.info("Generating Final Report...")
            
            # Generate Report
            if inspections_data:
                 try:
                    report_prompt = "Generate a summary report for this patrol based on the following inspections:\n\n"
                    
                    for item in inspections_data:
                        report_prompt += f"- Point: {item['point']}\n  Result: {item['result']}\n\n"
                    report_prompt += "Please provide a concise overview of the patrol status and any anomalies found."
                    
                    report_response_obj = ai_service.generate_report(report_prompt)
                    
                    report_text = ""
                    report_usage_str = "{}"
                    prompt_tokens = 0
                    candidate_tokens = 0
                    total_tokens = 0
                    
                    if isinstance(report_response_obj, dict) and "result" in report_response_obj:
                         report_text = report_response_obj["result"]
                         usage_data = report_response_obj.get("usage", {})
                         report_usage_str = json.dumps(usage_data)
                         prompt_tokens = usage_data.get("prompt_token_count", 0)
                         candidate_tokens = usage_data.get("candidates_token_count", 0)
                         total_tokens = usage_data.get("total_token_count", 0)
                    else:
                         report_text = str(report_response_obj)
                         report_usage_str = "{}"
                    
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute(
                        'UPDATE patrol_runs SET report_content = ?, token_usage = ?, prompt_tokens = ?, candidate_tokens = ?, total_tokens = ? WHERE id = ?', 
                        (report_text, report_usage_str, prompt_tokens, candidate_tokens, total_tokens, self.current_run_id)
                    )
                    conn.commit()
                    conn.close()
                    logger.info("Report generated and saved.")
                 except Exception as e:
                     logger.error(f"Report Generation Error: {e}")

            self.patrol_status = "Returning Home..."
            logger.info("Returning to charging station.")
            robot_service.return_home()
            time.sleep(2)
            self.patrol_status = "Finished"

        # Update Run Status
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE patrol_runs SET end_time = ?, status = ? WHERE id = ?', 
                    (get_current_time_str(), final_status, self.current_run_id))
        conn.commit()
        conn.close()
        
        logger.info(f"Patrol Run {self.current_run_id} finished with status: {final_status}")
        self.is_patrolling = False

patrol_service = PatrolService()

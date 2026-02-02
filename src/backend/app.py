import threading
import time
import io
import json
import os
from datetime import datetime
import flask
from flask import Flask, jsonify, request, send_file, render_template, send_from_directory
from PIL import Image

# New Modules
from config import *
from utils import load_json, save_json
from database import init_db, get_db_connection, save_generated_report
from robot_service import robot_service
from patrol_service import patrol_service
from ai_service import ai_service
from pdf_service import generate_patrol_report, generate_analysis_report

import logging

app = Flask(__name__, 
            template_folder=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'frontend', 'templates'),
            static_folder=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'frontend', 'static'))

# Ensure dirs
ensure_dirs()

# Logging
# Logging
# Use TimezoneFormatter for root logger or app logger
from logger import TimezoneFormatter

# Since basicConfig is tricky to override completely if handlers exist,
# let's just setup the root logger manually to match our needs.
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

if not root_logger.handlers:
    formatter = TimezoneFormatter('%(asctime)s %(levelname)s: %(message)s')
    
    # File handler for app.log
    file_handler = logging.FileHandler(os.path.join(LOG_DIR, "app.log"))
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # Console handler
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    root_logger.addHandler(stream_handler)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/state')
def get_state():
    return jsonify(robot_service.get_state())

@app.route('/api/map')
def get_map():
    map_bytes = robot_service.get_map_bytes()
    # print("Received request for /api/map")
    if map_bytes:
        # print(f"Serving map, size: {len(map_bytes)} bytes")
        return send_file(io.BytesIO(map_bytes), mimetype='image/png')
    else:
        # print("Map not not available yet")
        return "Map not available", 404

@app.route('/api/move', methods=['POST'])
def move_robot():
    data = request.json
    x = data.get('x')
    y = data.get('y')
    theta = data.get('theta', 0.0)
    
    if x is None or y is None:
        return jsonify({"error": "Missing x or y"}), 400
        
    if robot_service.move_to(x, y, theta, wait=False):
        return jsonify({"status": "Moving", "target": {"x": x, "y": y, "theta": theta}})
    else:
        return jsonify({"error": "Robot not connected or failed"}), 503

@app.route('/api/manual_control', methods=['POST'])
def manual_control():
    data = request.json
    action = data.get('action')
    
    try:
        if action == 'forward':
            robot_service.move_forward(distance=0.1, speed=0.1) 
        elif action == 'backward':
            robot_service.move_forward(distance=-0.1, speed=0.1)
        elif action == 'left':
            robot_service.rotate(angle=0.1745) # ~10 degrees
        elif action == 'right':
             robot_service.rotate(angle=-0.1745) # ~-10 degrees
        else:
            return jsonify({"error": "Invalid action"}), 400
            
        return jsonify({"status": "Command sent", "action": action})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/return_home', methods=['POST'])
def return_home():
    try:
        robot_service.return_home()
        return jsonify({"status": "Returning home"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/cancel_command', methods=['POST'])
def cancel_command():
    try:
        robot_service.cancel_command()
        return jsonify({"status": "Command cancelled"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def gen_frames(camera_func):
    while True:
        try:
            image = camera_func()
            if image:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + image.data + b'\r\n')
            time.sleep(0.05) # ~20fps
        except Exception as e:
            time.sleep(1)

@app.route('/api/camera/front')
def video_feed_front():
    return flask.Response(gen_frames(robot_service.get_front_camera_image),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/camera/back')
def video_feed_back():
    return flask.Response(gen_frames(robot_service.get_back_camera_image),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/test_ai', methods=['POST'])
def test_ai_route():
    try:
        img_response = robot_service.get_front_camera_image()
        if not img_response:
             return jsonify({"error": "Robot camera not available"}), 503

        image = Image.open(io.BytesIO(img_response.data))
        
        user_prompt = request.json.get('prompt', 'Describe what you see and check if everything is normal.')
        settings = load_json(SETTINGS_FILE, DEFAULT_SETTINGS)
        sys_prompt = settings.get('system_prompt', '')
        
        response_obj = ai_service.generate_inspection(image, user_prompt, sys_prompt)
        
        # Handle new structure
        if isinstance(response_obj, dict) and "result" in response_obj:
            result_text = response_obj["result"]
            usage_data = response_obj.get("usage", {})
        else:
            result_text = response_obj
            usage_data = {}

        return jsonify({"result": result_text, "prompt": user_prompt, "usage": usage_data})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- Patrol & Settings API ---

@app.route('/api/settings', methods=['GET', 'POST'])
def handle_settings():
    if request.method == 'POST':
        new_settings = request.json
        try:
            # Load existing settings to preserve keys not in prompt
            current_settings = load_json(SETTINGS_FILE, DEFAULT_SETTINGS)
            current_settings.update(new_settings)
            
            save_json(SETTINGS_FILE, current_settings)
            return jsonify({"status": "saved"})
        except Exception as e:
            logging.error(f"Failed to save settings: {e}")
            return jsonify({"error": f"Failed to save settings: {str(e)}"}), 500
    else:
        # Load file settings, but ensure all keys from DEFAULT_SETTINGS exist
        file_settings = load_json(SETTINGS_FILE, DEFAULT_SETTINGS)
        # Merge: Default < File
        final_settings = DEFAULT_SETTINGS.copy()
        final_settings.update(file_settings)
        return jsonify(final_settings)

@app.route('/api/points', methods=['GET', 'POST', 'DELETE'])
def handle_points():
    points = load_json(POINTS_FILE, [])
    if request.method == 'GET':
        return jsonify(points)
    elif request.method == 'POST':
        new_point = request.json
        if 'id' not in new_point:
            new_point['id'] = str(int(time.time() * 1000))

        updated = False
        for i, p in enumerate(points):
            if p.get('id') == new_point.get('id'):
                points[i] = new_point
                updated = True
                break
        if not updated:
            points.append(new_point)

        try:
            save_json(POINTS_FILE, points)
            return jsonify({"status": "saved", "id": new_point['id']})
        except Exception as e:
            logging.error(f"Failed to save points: {e}")
            return jsonify({"error": f"Failed to save points: {str(e)}"}), 500

    elif request.method == 'DELETE':
        point_id = request.args.get('id')
        points = [p for p in points if p.get('id') != point_id]
        try:
            save_json(POINTS_FILE, points)
            return jsonify({"status": "deleted"})
        except Exception as e:
            logging.error(f"Failed to delete point: {e}")
            return jsonify({"error": f"Failed to delete point: {str(e)}"}), 500

@app.route('/api/points/reorder', methods=['POST'])
def reorder_points():
    new_points = request.json
    if isinstance(new_points, list):
        try:
            save_json(POINTS_FILE, new_points)
            return jsonify({"status": "reordered"})
        except Exception as e:
            logging.error(f"Failed to reorder points: {e}")
            return jsonify({"error": f"Failed to reorder points: {str(e)}"}), 500
    return jsonify({"error": "Invalid format, expected list"}), 400

@app.route('/api/points/export', methods=['GET'])
def export_points():
    return send_file(POINTS_FILE, as_attachment=True, download_name='patrol_points.json')

@app.route('/api/points/import', methods=['POST'])
def import_points():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    if file:
        try:
            data = json.load(file)
            if isinstance(data, list):
                save_json(POINTS_FILE, data)
                return jsonify({"status": "imported", "count": len(data)})
            else:
                return jsonify({"error": "Invalid format, expected list"}), 400
        except Exception as e:
            return jsonify({"error": str(e)}), 400

@app.route('/api/points/from_robot', methods=['GET'])
def get_points_from_robot():
    """Fetch locations saved on the robot and merge with existing points"""
    try:
        # Get locations from robot
        robot_locations = robot_service.get_locations()
        if not robot_locations:
            return jsonify({"error": "No locations found on robot or robot not connected"}), 404

        # Load existing points
        existing_points = load_json(POINTS_FILE, [])

        # Helper function to compare coordinates (2 decimal places)
        def coords_match(p1, p2):
            return (round(p1.get('x', 0), 2) == round(p2.get('x', 0), 2) and
                    round(p1.get('y', 0), 2) == round(p2.get('y', 0), 2))

        # Check for duplicates and add new locations
        added = []
        skipped = []

        for loc in robot_locations:
            # Check if this location already exists (same name AND same coordinates)
            is_duplicate = False
            for existing in existing_points:
                if existing.get('name') == loc['name'] and coords_match(existing, loc):
                    is_duplicate = True
                    break

            if is_duplicate:
                skipped.append(loc['name'])
            else:
                # Add as new patrol point
                new_point = {
                    "id": str(int(time.time() * 1000)) + "_" + loc['id'][:8] if loc.get('id') else str(int(time.time() * 1000)),
                    "name": loc['name'],
                    "x": loc['x'],
                    "y": loc['y'],
                    "theta": loc.get('theta', 0.0),
                    "prompt": "Is everything normal?",
                    "enabled": True,
                    "source": "robot"
                }
                existing_points.append(new_point)
                added.append(loc['name'])

        # Save updated points
        if added:
            save_json(POINTS_FILE, existing_points)

        return jsonify({
            "status": "success",
            "added": added,
            "skipped": skipped,
            "total_robot_locations": len(robot_locations),
            "total_points": len(existing_points)
        })

    except Exception as e:
        logging.error(f"Error fetching locations from robot: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/patrol/status', methods=['GET'])
def get_patrol_status_route():
    return jsonify(patrol_service.get_status())

@app.route('/api/patrol/start', methods=['POST'])
def start_patrol_route():
    success, msg = patrol_service.start_patrol()
    if success:
        return jsonify({"status": "started"})
    else:
        return jsonify({"error": msg}), 400

@app.route('/api/patrol/stop', methods=['POST'])
def stop_patrol_route():
    patrol_service.stop_patrol()
    return jsonify({"status": "stopping"})

# --- Scheduled Patrol APIs ---

@app.route('/api/patrol/schedule', methods=['GET', 'POST'])
def handle_patrol_schedule():
    if request.method == 'GET':
        return jsonify(patrol_service.get_schedule())
    elif request.method == 'POST':
        data = request.json
        time_str = data.get('time')
        days = data.get('days')  # Optional: list of day numbers (0=Mon, 6=Sun)
        enabled = data.get('enabled', True)

        if not time_str:
            return jsonify({"error": "Time is required"}), 400

        # Validate time format
        try:
            datetime.strptime(time_str, "%H:%M")
        except ValueError:
            return jsonify({"error": "Invalid time format. Use HH:MM"}), 400

        schedule = patrol_service.add_schedule(time_str, days, enabled)
        return jsonify({"status": "added", "schedule": schedule})

@app.route('/api/patrol/schedule/<schedule_id>', methods=['PUT', 'DELETE'])
def handle_patrol_schedule_item(schedule_id):
    if request.method == 'PUT':
        data = request.json
        time_str = data.get('time')
        days = data.get('days')
        enabled = data.get('enabled')

        # Validate time format if provided
        if time_str:
            try:
                datetime.strptime(time_str, "%H:%M")
            except ValueError:
                return jsonify({"error": "Invalid time format. Use HH:MM"}), 400

        patrol_service.update_schedule(schedule_id, time_str, days, enabled)
        return jsonify({"status": "updated"})
    elif request.method == 'DELETE':
        patrol_service.delete_schedule(schedule_id)
        return jsonify({"status": "deleted"})

@app.route('/api/patrol/results', methods=['GET'])
def get_patrol_results():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT point_name, ai_response, timestamp FROM inspection_results ORDER BY id DESC LIMIT 20')
    rows = cursor.fetchall()
    conn.close()
    
    results = []
    for row in rows:
        results.append({
            "point_name": row[0],
            "result": row[1],
            "timestamp": row[2]
        })
    results.reverse()
    return jsonify(results)

# --- Stats APIs ---

@app.route('/api/stats/token_usage', methods=['GET'])
def get_token_usage_stats():
    # Optional filtering could be added here
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Get stats from patrol_runs
    query_runs = '''
        SELECT substr(start_time, 1, 10) as date, SUM(COALESCE(total_tokens, 0))
        FROM patrol_runs
        WHERE start_time IS NOT NULL
        GROUP BY substr(start_time, 1, 10)
    '''
    cursor.execute(query_runs)
    run_rows = cursor.fetchall()
    
    # 2. Get stats from generated_reports
    query_reports = '''
        SELECT substr(timestamp, 1, 10) as date, SUM(COALESCE(total_tokens, 0))
        FROM generated_reports
        WHERE timestamp IS NOT NULL
        GROUP BY substr(timestamp, 1, 10)
    '''
    cursor.execute(query_reports)
    report_rows = cursor.fetchall()
    
    conn.close()
    
    # Merge results
    usage_map = {}
    
    for row in run_rows:
        if row[0]:
            usage_map[row[0]] = usage_map.get(row[0], 0) + row[1]
            
    for row in report_rows:
        if row[0]:
            usage_map[row[0]] = usage_map.get(row[0], 0) + row[1]
    
    # Sort by date
    results = [{"date": k, "total": v} for k, v in sorted(usage_map.items())]
    return jsonify(results)


@app.route('/api/reports/generate', methods=['POST'])
def generate_report_route():
    data = request.json
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    user_prompt = data.get('prompt')
    
    if not start_date or not end_date:
        return jsonify({"error": "Start date and end date are required"}), 400
        
    try:
        # 1. Fetch Inspection Results
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Adjust end_date to include the full day (e.g. 2025-01-01 -> 2025-01-01 23:59:59)
        # Assuming inputs are YYYY-MM-DD
        query_start = f"{start_date} 00:00:00"
        query_end = f"{end_date} 23:59:59"
        
        cursor.execute('''
            SELECT point_name, result, timestamp, is_ng, description FROM (
                SELECT point_name, ai_response as result, timestamp, is_ng, ai_description as description 
                FROM inspection_results 
                WHERE timestamp BETWEEN ? AND ?
                ORDER BY timestamp ASC
            )
        ''', (query_start, query_end))
        
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
             return jsonify({"error": "No inspection data found for this period"}), 404
             
        # 2. Format Context
        context = f"Inspection Report Data ({start_date} to {end_date}):\n\n"
        for row in rows:
            status = "NG" if row['is_ng'] else "OK"
            context += f"- [{row['timestamp']}] Point: {row['point_name']} | Status: {status} | Details: {row['description'] or row['result']}\n"
            
        # 3. Call AI Service
        if not user_prompt:
             settings = load_json(SETTINGS_FILE, DEFAULT_SETTINGS)
             # Use get() but fallback to DEFAULT_SETTINGS value explicitly if key missing in file
             default_prompt = DEFAULT_SETTINGS.get('multiday_report_prompt', "Generate a concise summary report.")
             final_prompt = settings.get('multiday_report_prompt', default_prompt)
        else:
             final_prompt = user_prompt

        response = ai_service.generate_report(f"{final_prompt}\n\nContext:\n{context}")
        
        # 4. Save to Database
        report_id = save_generated_report(start_date, end_date, response['result'], response['usage'])
        
        return jsonify({
            "id": report_id,
            "report": response['result'],
            "usage": response['usage']
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/reports/generate/pdf', methods=['GET'])
def generate_multiday_report_pdf():
    """Generate PDF for multi-day analysis report from saved report."""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    if not start_date or not end_date:
        return jsonify({"error": "Start date and end date are required"}), 400

    try:
        # Fetch the most recent generated report for this date range
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT report_content FROM generated_reports
            WHERE start_date = ? AND end_date = ?
            ORDER BY timestamp DESC LIMIT 1
        ''', (start_date, end_date))
        row = cursor.fetchone()
        conn.close()

        if not row or not row['report_content']:
            return jsonify({"error": "No report found for this date range. Please generate a report first."}), 404

        report_content = row['report_content']

        # Generate PDF
        pdf_bytes = generate_analysis_report(
            content=report_content,
            start_date=start_date,
            end_date=end_date
        )

        # Return PDF file
        filename = f'analysis_report_{start_date}_{end_date}.pdf'
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        logging.error(f"Failed to generate PDF report: {e}")
        return jsonify({"error": f"Failed to generate PDF: {str(e)}"}), 500


# --- History APIs ---

@app.route('/api/history', methods=['GET'])
def get_history():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, start_time, end_time, status, robot_serial, report_content, model_id, total_tokens FROM patrol_runs ORDER BY id DESC')
    rows = cursor.fetchall()
    conn.close()
    
    result = []
    for row in rows:
        result.append(dict(row))
    return jsonify(result)

@app.route('/api/history/<int:run_id>', methods=['GET'])
def get_history_detail(run_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM patrol_runs WHERE id = ?', (run_id,))
    run = cursor.fetchone()
    if not run:
        conn.close()
        return jsonify({"error": "Run not found"}), 404
        
    cursor.execute('SELECT * FROM inspection_results WHERE run_id = ?', (run_id,))
    inspections = cursor.fetchall()
    conn.close()
    
    return jsonify({
        "run": dict(run),
        "inspections": [dict(i) for i in inspections]
    })

@app.route('/api/report/<int:run_id>/pdf')
def download_pdf_report(run_id):
    """Generate and download PDF report for a patrol run"""
    try:
        # Get start_time for filename
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT start_time FROM patrol_runs WHERE id = ?', (run_id,))
        row = cursor.fetchone()
        conn.close()

        if row and row['start_time']:
            # Format: 2025-01-15 14:30:00 -> 2025-01-15_143000
            start_time_str = row['start_time'].replace(' ', '_').replace(':', '')
            filename = f'patrol_report_{run_id}_{start_time_str}.pdf'
        else:
            filename = f'patrol_report_{run_id}.pdf'

        pdf_bytes = generate_patrol_report(run_id)
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logging.error(f"Failed to generate PDF for run {run_id}: {e}")
        return jsonify({"error": f"Failed to generate PDF: {str(e)}"}), 500

@app.route('/api/images/<path:filename>')
def serve_image(filename):
    return send_from_directory(IMAGES_DIR, filename)

if __name__ == '__main__':
    init_db()
    # The RobotService starts automatically on import but we might want to explicity connect?
    # It does auto-connect in polling loop.
    app.run(host='0.0.0.0', port=5000, debug=True)

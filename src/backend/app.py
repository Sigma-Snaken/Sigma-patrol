import threading
import time
import io
import json
import os
import flask
from flask import Flask, jsonify, request, send_file, render_template, send_from_directory
from PIL import Image

# New Modules
from config import *
from utils import load_json, save_json
from database import init_db, get_db_connection
from robot_service import robot_service
from patrol_service import patrol_service
from ai_service import ai_service

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
            save_json(SETTINGS_FILE, new_settings)
            return jsonify({"status": "saved"})
        except Exception as e:
            logging.error(f"Failed to save settings: {e}")
            return jsonify({"error": f"Failed to save settings: {str(e)}"}), 500
    else:
        return jsonify(load_json(SETTINGS_FILE, DEFAULT_SETTINGS))

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
    
    # Aggregate total_tokens by day (YYYY-MM-DD)
    # Ensure backward compatibility if total_tokens is NULL (use 0)
    query = '''
        SELECT substr(start_time, 1, 10) as date, SUM(COALESCE(total_tokens, 0))
        FROM patrol_runs
        WHERE start_time IS NOT NULL
        GROUP BY substr(start_time, 1, 10)
        ORDER BY date ASC
    '''
    
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()
    
    results = [{"date": row[0], "total": row[1]} for row in rows if row[0]]
    return jsonify(results)

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

@app.route('/api/images/<path:filename>')
def serve_image(filename):
    return send_from_directory(IMAGES_DIR, filename)

if __name__ == '__main__':
    init_db()
    # The RobotService starts automatically on import but we might want to explicity connect?
    # It does auto-connect in polling loop.
    app.run(host='0.0.0.0', port=5000, debug=True)

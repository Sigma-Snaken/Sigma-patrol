import threading
import time
import kachaka_api
from config import ROBOT_IP, SETTINGS_FILE, DEFAULT_SETTINGS
from utils import load_json

class RobotService:
    def __init__(self):
        self.client = None
        self.state_lock = threading.Lock()
        self.robot_state = {
            "battery": 0,
            "pose": {"x": 0.0, "y": 0.0, "theta": 0.0},
            "map_info": {
                "resolution": 0.05, 
                "width": 0, 
                "height": 0, 
                "origin_x": 0.0, 
                "origin_y": 0.0
            },
        }
        self.map_image_bytes = None
        
        # Start background polling
        self.polling_thread = threading.Thread(target=self._polling_loop, daemon=True)
        self.polling_thread.start()

    def connect(self):
        settings = load_json(SETTINGS_FILE, DEFAULT_SETTINGS)
        target_ip = settings.get("robot_ip", ROBOT_IP)
        
        try:
            self.client = kachaka_api.KachakaApiClient(target_ip)
            self.client.get_robot_serial_number()
            print(f"Connected to Kachaka at {target_ip}")
            return True
        except Exception as e:
            print(f"Failed to connect to Kachaka at {target_ip}: {e}")
            self.client = None
            return False

    def get_client(self):
        return self.client

    def _polling_loop(self):
        while True:
            if not self.client:
                self.connect()
                if not self.client:
                    time.sleep(2)
                    continue

            # Fetch map if missing
            if self.map_image_bytes is None:
                try:
                    png_map = self.client.get_png_map()
                    with self.state_lock:
                        self.map_image_bytes = png_map.data
                        self.robot_state["map_info"].update({
                            "resolution": png_map.resolution,
                            "width": png_map.width,
                            "height": png_map.height,
                            "origin_x": png_map.origin.x,
                            "origin_y": png_map.origin.y
                        })
                except Exception:
                    pass
            
            # Poll status
            try:
                pose = self.client.get_robot_pose()
                battery = self.client.get_battery_info()
                
                with self.state_lock:
                    actual_pose = getattr(pose, 'pose', pose)
                    self.robot_state["pose"].update({
                        "x": actual_pose.x,
                        "y": actual_pose.y,
                        "theta": actual_pose.theta
                    })

                    if isinstance(battery, tuple) and len(battery) > 0:
                         self.robot_state["battery"] = int(battery[0])
                    elif hasattr(battery, 'percentage'):
                        self.robot_state["battery"] = int(battery.percentage)
                    else:
                        self.robot_state["battery"] = int(battery) if isinstance(battery, (int, float)) else 0
                        
            except Exception:
                pass
            
            time.sleep(0.1)

    def get_state(self):
        with self.state_lock:
            return self.robot_state.copy()

    def get_map_bytes(self):
        return self.map_image_bytes

    def move_to(self, x, y, theta, wait=True):
        if self.client:
            return self.client.move_to_pose(x, y, theta, wait_for_completion=wait)
        return None
        
    def move_forward(self, distance, speed=0.1):
         if self.client:
            self.client.move_forward(distance_meter=distance, speed=speed)

    def rotate(self, angle):
        if self.client:
            self.client.rotate_in_place(angle_radian=angle)

    def return_home(self):
        if self.client:
            self.client.return_home()
            
    def cancel_command(self):
        if self.client:
            self.client.cancel_command()

    def get_front_camera_image(self):
        if self.client:
             return self.client.get_front_camera_ros_compressed_image()
        return None

    def get_back_camera_image(self):
        if self.client:
             return self.client.get_back_camera_ros_compressed_image()
        return None
        
    def get_serial(self):
        if self.client:
            return self.client.get_robot_serial_number()
        return "unknown"

# Singleton instance
robot_service = RobotService()

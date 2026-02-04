
import threading
import time
import cv2
import numpy as np
import io
from PIL import Image
from logger import get_logger

logger = get_logger("video_recorder", "video_recorder.log")

class VideoRecorder:
    def __init__(self, output_path, frame_func, fps=5.0, width=640, height=480):
        self.output_path = output_path
        self.frame_func = frame_func
        self.fps = fps
        self.width = width
        self.height = height
        self.is_recording = False
        self.thread = None
        self.writer = None

    def start(self):
        if self.is_recording:
            return
        
        try:
            # Try codecs in order of preference.
            # H.264 (avc1) is best for browser/IDE compatibility but may
            # not be available on all platforms (e.g. ARM without hw encoder).
            if self.output_path.endswith('.mp4'):
                codecs = [('avc1', 'H.264'), ('XVID', 'XVID'), ('MJPG', 'MJPEG')]
            else:
                codecs = [('MJPG', 'MJPEG')]

            for codec_tag, codec_name in codecs:
                fourcc = cv2.VideoWriter_fourcc(*codec_tag)
                self.writer = cv2.VideoWriter(
                    self.output_path, fourcc, self.fps, (self.width, self.height)
                )
                if self.writer.isOpened():
                    logger.info(f"Using {codec_name} codec for {self.output_path}")
                    break
                self.writer.release()
                logger.warning(f"{codec_name} codec unavailable, trying next...")
                self.writer = None

            if self.writer is None or not self.writer.isOpened():
                logger.error(f"Failed to open video writer for {self.output_path}")
                return

            self.is_recording = True
            self.thread = threading.Thread(target=self._record_loop, daemon=True)
            self.thread.start()
            logger.info(f"Started video recording: {self.output_path}")
            
        except Exception as e:
            logger.error(f"Failed to start video recording: {e}")

    def stop(self):
        if not self.is_recording:
            return
        
        self.is_recording = False
        if self.thread:
            self.thread.join(timeout=5)
            self.thread = None
            
        if self.writer:
            self.writer.release()
            self.writer = None
            
        logger.info("Stopped video recording")

    def _record_loop(self):
        interval = 1.0 / self.fps
        
        while self.is_recording:
            start_time = time.time()
            
            try:
                # Get frame from robot service
                ros_image = self.frame_func()
                
                if ros_image:
                    # Convert bytes to PIL Image
                    image = Image.open(io.BytesIO(ros_image.data))
                    
                    # Resize if needed (naive resize for now)
                    if image.size != (self.width, self.height):
                         image = image.resize((self.width, self.height))
                    
                    # Convert to numpy array (RGB)
                    frame_rgb = np.array(image)
                    
                    # Convert to BGR for OpenCV
                    frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
                    
                    if self.writer:
                        self.writer.write(frame_bgr)
                        
            except Exception as e:
                logger.error(f"Error recording frame: {e}")
                
            # Maintain FPS
            elapsed = time.time() - start_time
            sleep_time = max(0, interval - elapsed)
            time.sleep(sleep_time)

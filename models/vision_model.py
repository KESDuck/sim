import cv2 as cv
from PyQt5.QtCore import QObject, pyqtSignal, QThread, QMutex
import time

from utils.logger_config import get_logger
from models.camera import CameraHandler
from utils.tools import determine_bound, sort_centroids

logger = get_logger("Vision")

class LiveCameraWorker(QThread):
    """
    Worker thread for live camera view only.
    This avoids UI freezing during continuous camera display.
    """
    frame_ready = pyqtSignal(object)  # Signal to emit when a frame is captured
    error_occurred = pyqtSignal(str)  # Signal for error reporting

    def __init__(self, camera):
        super().__init__()
        self.camera = camera
        self.mutex = QMutex()
        self.stopped = False
        self.paused = True
        
        # For tracking consecutive failures
        self.consecutive_failures = 0
        self.max_failures = 3
        
    def run(self):
        """Thread main loop for live camera feed"""
        while not self.stopped:
            self.mutex.lock()
            is_paused = self.paused
            self.mutex.unlock()
            
            if is_paused:
                time.sleep(0.1)  # Sleep while paused
                continue
                
            try:
                frame = self.camera.get_frame()
                if frame is not None:
                    self.frame_ready.emit(frame)
                    self.consecutive_failures = 0
                else:
                    self.consecutive_failures += 1
                    if self.consecutive_failures >= self.max_failures:
                        # Just report the error, don't try to reconnect automatically
                        self.error_occurred.emit("Camera not responding - use reconnect button if needed")
                        self.consecutive_failures = 0
                        # Add delay to prevent too many error messages
                        time.sleep(1.0)
            except Exception as e:
                self.error_occurred.emit(f"Camera error: {str(e)}")
                time.sleep(0.5)
                
            time.sleep(0.03)  # ~30fps with some overhead
        
    def pause(self):
        """Pause the live feed"""
        self.mutex.lock()
        self.paused = True
        self.mutex.unlock()
        
    def resume(self):
        """Resume the live feed"""
        self.mutex.lock()
        self.paused = False
        self.mutex.unlock()
        
    def stop(self):
        """Stop the worker thread"""
        self.mutex.lock()
        self.stopped = True
        self.mutex.unlock()
        self.wait()

class VisionModel(QObject):
    """
    Model that handles vision processing.
    Captures frames and processes them to identify centroids.
    Live view runs in a thread, but processing is synchronous.
    """
    # Define signals for communication with controller
    frame_processed = pyqtSignal(bool)  # Signal to indicate processing completion
    
    def __init__(self, cam_type):
        super().__init__()
        self.camera = CameraHandler(cam_type=cam_type)
        if self.camera.initialize_camera():
            # Get first frame to verify camera
            self.get_first_frame()

        # Setup the live camera worker thread
        self.live_worker = LiveCameraWorker(self.camera)
        self.live_worker.frame_ready.connect(self.handle_live_frame)
        self.live_worker.error_occurred.connect(self.handle_error)
        self.live_worker.start()
        
        # image frame and points
        self.frame_camera_live = None  # right after undistort
        self.frame_camera_stored = None
        self.frame_threshold = None  # right after threshold
        self.frame_contour = None  # with contour
        self.centroids = None  # list of centroids

    def get_first_frame(self):
        """Get first frame to verify camera operation"""
        frame = self.camera.get_frame()
        if frame is not None:
            logger.info(f"Frame shape: {frame.shape}")
        else:
            logger.error("Failed to get first frame from camera")

    def live_capture(self) -> bool:
        """
        Start live capture mode
        """
        self.live_worker.resume()
        return True
        
    def stop_live_capture(self):
        """
        Stop live capture mode
        """
        self.live_worker.pause()

    def handle_live_frame(self, frame):
        """Handle frames from the worker in live mode"""
        self.frame_camera_live = frame

    def capture_and_process(self) -> bool:
        """
        Capture frame and process to find centroids
        This is a blocking call - UI will freeze during processing
        Returns True if capture and process succeed else False
        """
        # Ensure live worker is paused to avoid camera conflicts
        self.live_worker.pause()
        
        # Parameters for processing
        threshold_value = 135
        min_area = 6000  # around 80*80
        max_area = 10000  # 100 * 100
        crop_region = None
        
        # Try multiple times to get a valid frame
        frame = None
        frame = self.camera.get_frame()

        if frame is None:
            logger.error("Failed to capture frame for processing")
            self.frame_processed.emit(False)
            return False

        self.frame_camera_stored = frame
            
        # threshold
        _, thres = cv.threshold(frame, 0, 255, cv.THRESH_BINARY + cv.THRESH_OTSU)

        # contours
        contours, _ = cv.findContours(thres, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)

        # Filter Contours based on contour area
        filtered_contours = [cnt for cnt in contours if min_area < cv.contourArea(cnt) < max_area]

        # Find Centroids
        centroids = []
        filtered_contours_2 = []  # based on selected centroids
        for cnt in filtered_contours:
            x, y, w, h = cv.boundingRect(cnt)
            aspect_ratio = w / h
            if 0.8 <= aspect_ratio <= 1.2:
                M = cv.moments(cnt)
                if M["m00"] != 0:
                    cX = int(M["m10"] / M["m00"])
                    cY = int(M["m01"] / M["m00"])
                    if determine_bound((cX, cY), crop_region):
                        filtered_contours_2.append(cnt)
                        centroids.append((cX, cY))

        # Prepare result frames
        self.frame_threshold = cv.cvtColor(thres, cv.COLOR_GRAY2BGR)
        
        contour_overlay = self.frame_threshold.copy()
        for cnt in filtered_contours_2:  # Draw the contours
            cv.drawContours(contour_overlay, [cnt], -1, (0, 255, 0), 2)  # Green for contours
            
        self.frame_contour = contour_overlay
        self.centroids = sort_centroids(centroids)
        
        logger.info(f"Total centroids found: {len(self.centroids)}")
        
        # Signal processing complete
        self.frame_processed.emit(True)
        return True

    def handle_error(self, error_message):
        """Handle errors from the live camera worker"""
        logger.error(f"Camera worker error: {error_message}")
        
    def close(self):
        """Clean up resources"""
        # Stop the worker thread
        if hasattr(self, 'live_worker'):
            self.live_worker.stop()
            
        # Release the camera
        if hasattr(self.camera, 'release') and callable(self.camera.release):
            self.camera.release() 
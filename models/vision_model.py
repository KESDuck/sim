import cv2 as cv
from PyQt5.QtCore import QObject, pyqtSignal
import time
import yaml
import numpy as np

from utils.logger_config import get_logger
from models.camera import CameraHandler
from utils.tools import determine_bound

logger = get_logger("Vision")

with open('config.yml', 'r') as file:
    config = yaml.safe_load(file)

class VisionModel(QObject):
    """
    Model that handles vision processing.
    Captures frames and processes them to identify centroids.
    """
    # Define signals for communication with controller
    frame_processed = pyqtSignal(bool)  # Signal to indicate processing completion
    
    def __init__(self, cam_type):
        super().__init__()
        self.camera = CameraHandler(cam_type=cam_type)
        if self.camera.initialize_camera():
            # Get first frame to verify camera
            self.get_first_frame()
        
        # image frame and points
        self.frame_camera_stored = np.zeros((1944, 2592, 3), dtype=np.uint8)  # Initialize with black frame
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

    def capture_and_process(self) -> bool:
        """
        Capture frame and process to find centroids
        This is a blocking call - UI will freeze during processing
        Returns True if capture and process succeed else False
        """
        # Parameters for processing
        threshold_value = 135
        min_area = 2700  # 52x52
        max_area = 5625  # 75x75
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
        
        # Save centroids to instance variable
        self.centroids = centroids
        
        logger.info(f"Total centroids found: {len(self.centroids)}")
        
        # Signal processing complete
        self.frame_processed.emit(True)
        return True
        
    def close(self):
        """Clean up resources"""
        # Release the camera
        if hasattr(self.camera, 'release') and callable(self.camera.release):
            self.camera.release() 
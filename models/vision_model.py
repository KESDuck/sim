import cv2 as cv
from PyQt5.QtCore import QObject, pyqtSignal

from utils.logger_config import get_logger
from models.camera import CameraHandler
from utils.tools import determine_bound, sort_centroids

logger = get_logger("Vision")

class VisionModel(QObject):
    """
    Model that handles vision processing.
    Captures frames and processes them to identify centroids.
    """
    def __init__(self, cam_type):
        super().__init__()
        self.camera = CameraHandler(cam_type=cam_type, camera_matrix=None, dist_coeffs=None)
        self.get_first_frame()

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
        Get camera frame without processing
        """
        self.frame_camera_live = self.camera.get_frame()  # grayscale image
        if self.frame_camera_live is None:
            return False
        return True

    def capture_and_process(self) -> bool:
        """
        Capture frame and process to find centroids
        Returns True if capture and process succeed else False
        """
        # TODO: add these to param
        threshold_value = 135
        min_area = 6000  # around 80*80
        max_area = 10000  # 100 * 100
        crop_region = None
        alpha = 0.5

        self.frame_camera_stored = self.camera.get_frame()
        if self.frame_camera_stored is None:
            return False

        # threshold
        _, thres = cv.threshold(self.frame_camera_stored, 0, 255, cv.THRESH_BINARY + cv.THRESH_OTSU)

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

        ##### SAVING #####
        # All the converting and returning
        self.frame_threshold = cv.cvtColor(thres, cv.COLOR_GRAY2BGR)

        contour_overlay = self.frame_threshold.copy()
        for cnt in filtered_contours_2:  # Draw the contours
            cv.drawContours(contour_overlay, [cnt], -1, (0, 255, 0), 2)  # Green for contours

        self.frame_contour = contour_overlay
        self.centroids = sort_centroids(centroids)

        logger.info(f"Total centroids found: {len(self.centroids)}")

        return True

    def close(self):
        # Release the camera
        if hasattr(self.camera, 'release') and callable(self.camera.release):
            self.camera.release() 
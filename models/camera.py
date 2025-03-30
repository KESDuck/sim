import os
import sys
import cv2 as cv
from abc import ABC, abstractmethod
import yaml

# Add the project root directory to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from utils.logger_config import get_logger

# Import pylon directly
from pypylon import pylon

logger = get_logger("Camera")
with open('config.yml', 'r') as file:
    config = yaml.safe_load(file)

# Abstract Base Class
class CameraBase(ABC):
    """
    Abstract base class for all camera types.
    """
    @abstractmethod
    def get_frame(self):
        """
        Capture and preprocess a frame.
        Return None if no frame
        """
        pass

    @abstractmethod
    def release(self):
        """Release camera resources."""
        pass

# USB Camera Class
class USBCamera(CameraBase):
    """
    Handles USB camera operations, including frame capture and preprocessing.
    """
    def __init__(self, cam_num=0, camera_matrix=None, dist_coeffs=None):
        self.cap = cv.VideoCapture(cam_num)
        if not self.cap.isOpened():
            logger.error(f"Failed to initialize USB camera {cam_num}.")
            raise RuntimeError(f"Failed to initialize USB camera {cam_num}.")
        self.camera_matrix = camera_matrix
        self.dist_coeffs = dist_coeffs
        logger.info(f"##### USB camera {cam_num} initialized. #####")

    def get_frame(self):
        """Capture and preprocess a frame from the USB camera."""
        ret, frame = self.cap.read()
        if not ret:
            logger.error("Failed to capture frame from USB camera.")
            return None

        frame_gray = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)
        return self._undistort(frame_gray)

    def _undistort(self, frame):
        """Undistort the frame if calibration data is provided."""
        if self.camera_matrix is not None and self.dist_coeffs is not None:
            logger.info("Applying undistortion to USB frame.")
            return cv.undistort(frame, self.camera_matrix, self.dist_coeffs)
        return frame

    def release(self):
        """Release the USB camera."""
        self.cap.release()
        logger.info("USB camera released.")

# Pylon Camera Class
class PylonCamera(CameraBase):
    """
    Handles Pylon camera operations, including frame capture and preprocessing.
    TODO: add retry logic
    """
    def __init__(self, camera_index=0):
        super().__init__()
        # Initialize the pylon camera directly
        self.camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())
        self.camera.Open()
        # Start grabbing in continuous mode
        self.camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
        logger.info("Pylon camera initialized.")

    def get_frame(self):
        # Capture a frame from the pylon camera
        if not self.camera.IsGrabbing():
            self.camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
        
        # Retrieve the frame with a timeout
        grab_result = self.camera.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)
        if grab_result.GrabSucceeded():
            frame = grab_result.Array
            grab_result.Release()
            return frame
        else:
            logger.error("Failed to grab frame from Pylon camera.")
            grab_result.Release()
            return None

    def release(self):
        """Release the Pylon camera."""
        if hasattr(self, 'camera') and self.camera:
            if self.camera.IsGrabbing():
                self.camera.StopGrabbing()
            self.camera.Close()
            logger.info("Pylon camera released.")

class FileMockInterface:
    def __init__(self, path):
        self.path = path
        print("##### MOCK CAMERA INITIALIZED #####")

    def get_frame(self):
        """TODO: return none if cannot read"""
        return cv.imread(self.path, cv.IMREAD_GRAYSCALE)

    def release(self):
        pass


# Camera Handler Class
class CameraHandler:
    """
    Delegates camera operations to the appropriate camera type (USB or Pylon).
    """
    def __init__(self, cam_type="usb", cam_num=None, camera_matrix=None, dist_coeffs=None):
        self.camera = None
        self.camera_connected = False
        
        if cam_num is None:
            cam_num = config.get("cam_num", 0)
            
        try:
            if cam_type == "usb":
                self.camera = USBCamera(cam_num, camera_matrix, dist_coeffs)
                self.camera_connected = True
            elif cam_type == "pylon":
                self.camera = PylonCamera(camera_index=0)
                self.camera_connected = True
            
            if cam_type == "file":
                img_path = config.get("img_path", "save/default.jpg")
                logger.info(f"Using file camera with image: {img_path}")
                self.camera = FileMockInterface(path=img_path)
                self.camera_connected = True
            
            if not self.camera_connected:
                logger.error(f"Unsupported camera type: {cam_type}")
        except Exception as e:
            logger.error(f"Failed to initialize {cam_type} camera: {e}")
            logger.info("Falling back to file camera")
            try:
                img_path = config.get("img_path", "save/default.jpg")
                self.camera = FileMockInterface(path=img_path)
                self.camera_connected = True
            except Exception as e2:
                logger.error(f"Failed to initialize file camera as fallback: {e2}")
                self.camera_connected = False

    def get_frame(self):
        """Delegate frame capture to the selected camera."""
        if not self.camera_connected:
            logger.error("Camera not connected")
            return None
        try:
            return self.camera.get_frame()
        except Exception as e:
            logger.error(f"Error getting frame: {e}")
            return None

    def release(self):
        """Delegate resource cleanup to the selected camera."""
        if self.camera_connected and self.camera:
            try:
                self.camera.release()
            except Exception as e:
                logger.error(f"Error releasing camera: {e}")

if __name__ == "__main__":
    camera = CameraHandler(cam_type="pylon")
    test_frame = camera.get_frame()
    if test_frame is not None:
        print(f"Frame shape: {test_frame.shape}")
    else:
        print("No frame captured")

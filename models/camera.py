import os
import sys
import cv2 as cv
from abc import ABC, abstractmethod
import yaml

try:
    from pypylon import pylon
    PYLON_AVAILABLE = True
except ImportError:
    PYLON_AVAILABLE = False

# Add the project root directory to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from utils.logger_config import get_logger

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
    def __init__(self, camera_matrix=None, dist_coeffs=None):
        if not PYLON_AVAILABLE:
            logger.error("Pypylon library not available. Cannot use Pylon camera.")
            raise ImportError("Pypylon library not available")
            
        self.camera = None
        self.connect_pylon_camera()
        self.camera_matrix = camera_matrix
        self.dist_coeffs = dist_coeffs

    def get_frame(self):
        """Capture and preprocess a frame from the Pylon camera."""
        try:
            grab_result = self.camera.GrabOne(4000)  # Timeout in milliseconds
            if not grab_result.GrabSucceeded():
                logger.error("Failed to capture frame from Pylon camera.")
                return None

            return self._undistort(grab_result.Array)
        
        except pylon.RuntimeException as e:
            # logger.error(f"{e}")
            # TODO this happens often, see how to not to use try except
            self.connect_pylon_camera()
            return None

    def _undistort(self, frame):
        """Undistort the frame if calibration data is provided."""
        if self.camera_matrix is not None and self.dist_coeffs is not None:
            logger.info("Applying undistortion to Pylon frame.")
            return cv.undistort(frame, self.camera_matrix, self.dist_coeffs)
        return frame

    def connect_pylon_camera(self):
        """Safely release and reconnect the camera."""
        try:
            if hasattr(self, 'camera') and self.camera:
                self.release()
            self.camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())
            if not self.camera:
                logger.error("No Pylon camera found.")
                raise RuntimeError("No Pylon camera found.")
            self.camera.Open()
            model_name = self.camera.GetDeviceInfo().GetModelName()
            camera_ip = self.camera.GetDeviceInfo().GetIpAddress()
            logger.info(f"##### Pylon camera connected: {model_name} ({camera_ip}) #####")
        except Exception as e:
            logger.error(f"Failed to connect to Pylon camera: {e}")
            raise RuntimeError(f"Failed to connect to Pylon camera: {e}")

    def release(self):
        """Release the Pylon camera."""
        if hasattr(self, 'camera') and self.camera:
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
                if not PYLON_AVAILABLE:
                    logger.error("Pypylon library not available. Falling back to file camera.")
                    cam_type = "file"
                else:
                    self.camera = PylonCamera(camera_matrix, dist_coeffs)
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
    camera = CameraHandler(cam_type="file")
    test_frame = camera.get_frame()
    if test_frame is not None:
        print(f"Frame shape: {test_frame.shape}")
    else:
        print("No frame captured")

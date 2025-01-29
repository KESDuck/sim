from abc import ABC, abstractmethod
import cv2 as cv
from pypylon import pylon
from logger_config import get_logger

logger = get_logger("Camera")

# Abstract Base Class
class CameraBase(ABC):
    """
    Abstract base class for all camera types.
    """
    @abstractmethod
    def get_frame(self):
        """Capture and preprocess a frame."""
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
            raise RuntimeError(f"Failed to initialize USB camera {cam_num}.")
        self.camera_matrix = camera_matrix
        self.dist_coeffs = dist_coeffs
        logger.info(f"USB camera {cam_num} initialized.")

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
    """
    def __init__(self, camera_matrix=None, dist_coeffs=None):
        self.camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())
        self.camera.Open()
        self.camera_matrix = camera_matrix
        self.dist_coeffs = dist_coeffs
        logger.info(f"Pylon camera connected: {self.camera.GetDeviceInfo().GetModelName()}")

    def get_frame(self):
        """Capture and preprocess a frame from the Pylon camera."""
        grab_result = self.camera.GrabOne(4000)  # Timeout in milliseconds
        if not grab_result.GrabSucceeded():
            logger.error("Failed to capture frame from Pylon camera.")
            return None

        return self._undistort(grab_result.Array)

    def _undistort(self, frame):
        """Undistort the frame if calibration data is provided."""
        if self.camera_matrix is not None and self.dist_coeffs is not None:
            logger.info("Applying undistortion to Pylon frame.")
            return cv.undistort(frame, self.camera_matrix, self.dist_coeffs)
        return frame

    def release(self):
        """Release the Pylon camera."""
        self.camera.Close()
        logger.info("Pylon camera released.")

# Camera Handler Class
class CameraHandler:
    """
    Delegates camera operations to the appropriate camera type (USB or Pylon).
    """
    def __init__(self, cam_type="usb", cam_num=0, camera_matrix=None, dist_coeffs=None):
        if cam_type == "usb":
            self.camera = USBCamera(cam_num, camera_matrix, dist_coeffs)
        elif cam_type == "pylon":
            self.camera = PylonCamera(camera_matrix, dist_coeffs)
        else:
            raise ValueError(f"Unsupported camera type: {cam_type}")
        logger.info(f"CameraHandler initialized with {cam_type} camera.")

    def get_frame(self):
        """Delegate frame capture to the selected camera."""
        return self.camera.get_frame()

    def release(self):
        """Delegate resource cleanup to the selected camera."""
        self.camera.release()

if __name__ == "__main__":
    camera = CameraHandler(cam_type="usb")
    test_frame = camera.get_frame()
    print(test_frame[0])

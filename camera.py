from abc import ABC, abstractmethod
import cv2 as cv
from pypylon import pylon
from logger_config import get_logger
import yaml

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
    def __init__(self, cam_type="usb", cam_num=0, camera_matrix=None, dist_coeffs=None):
        self.camera = None
        self.camera_connected = False
        try:
            if cam_type == "usb":
                self.camera = USBCamera(cam_num, camera_matrix, dist_coeffs)
                self.camera_connected = True
            elif cam_type == "pylon":
                self.camera = PylonCamera(camera_matrix, dist_coeffs)
                self.camera_connected = True
            elif cam_type == "file":
                self.camera = FileMockInterface(path=config["img_path"])
                self.camera_connected = True
            else:
                logger.error(f"Unsupported camera type: {cam_type}")
                return
        except Exception as e:
            logger.error(f"Failed to initialize {cam_type} camera: {e}")
            self.camera_connected = False

    def get_frame(self):
        """Delegate frame capture to the selected camera."""
        if not self.camera_connected:
            return None
        return self.camera.get_frame()

    def release(self):
        """Delegate resource cleanup to the selected camera."""
        if self.camera_connected and self.camera:
            self.camera.release()

if __name__ == "__main__":
    camera = CameraHandler(cam_type="pylon")
    test_frame = camera.get_frame()
    print(test_frame[0])

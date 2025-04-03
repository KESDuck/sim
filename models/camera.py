import os
import sys
import cv2 as cv
from abc import ABC, abstractmethod
import yaml
import time

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
    """
    def __init__(self):
        super().__init__()
        self.camera = None
        self.consecutive_failures = 0
        self.max_frame_failures = 5
        self.is_reconnecting = False
        self.grab_timeout_ms = 5000  # Increase timeout to 5 seconds
        self.reconnect()

    def reconnect(self, max_attempts=2):
        """Attempt to connect to the Pylon camera with a maximum number of attempts."""
        if self.is_reconnecting:
            logger.warning("Already attempting to reconnect, skipping duplicate request")
            return False
            
        self.is_reconnecting = True
        attempt = 0
        success = False
        
        try:
            while attempt < max_attempts:
                try:
                    # Make sure any existing camera is properly closed
                    if self.camera:
                        if self.camera.IsGrabbing():
                            try:
                                self.camera.StopGrabbing()
                            except Exception as e:
                                logger.warning(f"Error stopping grabbing: {e}")
                                
                        if self.camera.IsOpen():
                            try:
                                self.camera.Close()
                            except Exception as e:
                                logger.warning(f"Error closing camera: {e}")
                    
                    # Get device list and make sure there's at least one device
                    tl_factory = pylon.TlFactory.GetInstance()
                    devices = tl_factory.EnumerateDevices()
                    if len(devices) == 0:
                        logger.error("No Pylon cameras found")
                        attempt += 1
                        time.sleep(1)  # Longer delay
                        continue
                    
                    # Create and open camera with the first device
                    self.camera = pylon.InstantCamera(tl_factory.CreateDevice(devices[0]))
                    self.camera.Open()

                    # Don't try to set advanced parameters that might fail
                    model_name = self.camera.GetDeviceInfo().GetModelName()
                    camera_ip = self.camera.GetDeviceInfo().GetIpAddress()
                    logger.info(f"##### Pylon camera connected: {model_name} ({camera_ip}) #####")
                    
                    # Start grabbing after configuration
                    self.camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
                    self.consecutive_failures = 0
                    
                    # Try a simple test frame capture
                    test_frame = self._grab_frame()
                    if test_frame is not None:
                        success = True
                        break
                    else:
                        logger.warning("Camera connected but test frame capture failed")
                        attempt += 1
                    
                except Exception as e:
                    logger.error(f"Error connecting to Pylon camera: {e}")
                    attempt += 1
                    if attempt >= max_attempts:
                        break
                    time.sleep(0.5)  # Wait before retrying
        finally:
            self.is_reconnecting = False
            
        if not success and self.camera and self.camera.IsOpen():
            try:
                if self.camera.IsGrabbing():
                    self.camera.StopGrabbing()
                self.camera.Close()
            except Exception:
                pass
                
        return success
        
    def _grab_frame(self):
        """Internal grab frame method with error handling"""
        if not self.camera or not self.camera.IsOpen() or not self.camera.IsGrabbing():
            return None
            
        try:
            grab_result = self.camera.RetrieveResult(self.grab_timeout_ms, pylon.TimeoutHandling_ThrowException)
            if grab_result and grab_result.GrabSucceeded():
                frame = grab_result.Array
                grab_result.Release()
                return frame
            else:
                if grab_result:
                    error_desc = grab_result.ErrorDescription
                    grab_result.Release()
                    logger.debug(f"Frame grab failed: {error_desc}")
                return None
        except pylon.TimeoutException:
            logger.debug("Frame grab timeout")
            return None
        except Exception as e:
            logger.warning(f"Error in grab frame: {e}")
            return None

    def get_frame(self):
        """Capture a single frame from the Pylon camera."""
        if not self.camera or not self.camera.IsGrabbing():
            # Camera not initialized or not grabbing - don't auto-reconnect
            logger.error("Camera is not initialized or not grabbing")
            return None
            
        frame = self._grab_frame()
        
        if frame is not None:
            self.consecutive_failures = 0
            return frame
        else:
            self.consecutive_failures += 1
            
            # Just log the error, don't auto-reconnect
            if self.consecutive_failures >= self.max_frame_failures:
                logger.warning(f"Failed to grab {self.consecutive_failures} frames")
                self.consecutive_failures = 0
            return None

    def release(self):
        """Release the Pylon camera."""
        if self.camera:
            try:
                if self.camera.IsGrabbing():
                    self.camera.StopGrabbing()
                if self.camera.IsOpen():
                    self.camera.Close()
                logger.info("Pylon camera released")
            except Exception as e:
                logger.error(f"Error releasing Pylon camera: {e}")
        self.camera = None

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
        self.cam_type = cam_type
        self.cam_num = cam_num if cam_num is not None else config.get("cam_num", 0)
        self.camera_matrix = camera_matrix
        self.dist_coeffs = dist_coeffs
        self._initialize_camera()

    def _initialize_camera(self):
        """Initialize the appropriate camera type."""
        try:
            if self.cam_type == "usb":
                self.camera = USBCamera(self.cam_num, self.camera_matrix, self.dist_coeffs)
            elif self.cam_type == "pylon":
                self.camera = PylonCamera()
            else:
                logger.error(f"Unsupported camera type: {self.cam_type}")
        except Exception as e:
            logger.error(f"Failed to initialize {self.cam_type} camera: {e}")
            self.camera = None

    def get_frame(self):
        """Delegate frame capture to the selected camera."""
        return None if self.camera is None else self.camera.get_frame()

    def release(self):
        """Delegate resource cleanup to the selected camera."""
        if self.camera:
            self.camera.release()
            self.camera = None
            
    def reconnect(self, max_attempts=2):
        """Reconnect the camera by releasing and reinitializing it."""
        logger.info(f"Reconnecting {self.cam_type} camera...")
        self.release()
        
        # Pylon camera already has retry attempts in its reconnect method
        # For USB camera we'll need to retry here
        for attempt in range(max_attempts):
            # Small delay before reconnection 
            time.sleep(0.5)
            self._initialize_camera()
            
            # Check if reconnection was successful
            if self.camera is not None:
                test_frame = self.get_frame()
                if test_frame is not None:
                    logger.info(f"Successfully reconnected {self.cam_type} camera")
                    return True
                else:
                    logger.warning(f"Reconnection attempt {attempt+1}/{max_attempts}: Camera initialized but no valid frame")
            else:
                logger.warning(f"Reconnection attempt {attempt+1}/{max_attempts}: Failed to initialize camera")
        
        logger.error(f"Reconnection failed after {max_attempts} attempts")
        return False

if __name__ == "__main__":
    camera = CameraHandler(cam_type="pylon")
    test_frame = camera.get_frame()
    if test_frame is not None:
        print(f"Frame shape: {test_frame.shape}")
    else:
        print("No frame captured")

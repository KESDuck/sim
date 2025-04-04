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

# Pylon camera event handlers
class PylonImageHandler(pylon.ImageEventHandler):
    """
    Event handler for Pylon camera image events.
    Processes images as they are captured by the camera.
    """
    def __init__(self):
        super().__init__()
        self.last_image = None
        self.image_ready = False
        self.success_count = 0
        self.fail_count = 0
        self.last_timestamp = time.time()
        
    def OnImageGrabbed(self, camera, grabResult):
        """Called when an image is grabbed from the camera."""
        if grabResult.GrabSucceeded():
            # Store the image array
            self.last_image = grabResult.Array
            self.image_ready = True
            self.success_count += 1
            
            # Log performance statistics
            current_time = time.time()
            elapsed = current_time - self.last_timestamp
            self.last_timestamp = current_time
            
            # logger.debug(f"Frame grabbed: {elapsed:.3f}s, Success rate: {self.success_count/(self.success_count+self.fail_count):.1%}")
        else:
            self.fail_count += 1
            # logger.debug(f"Grab failed: {grabResult.ErrorDescription}")
            
    def get_last_image(self):
        """Returns the last successfully grabbed image and resets the ready flag."""
        if self.image_ready:
            self.image_ready = False
            return self.last_image
        return None

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
    Handles Pylon camera operations using an event-driven approach.
    Images are automatically processed by ImageHandler when they arrive from the camera.
    """
    def __init__(self):
        super().__init__()
        self.camera = None
        self.image_handler = None
        self.consecutive_failures = 0
        self.max_frame_failures = 5
        self.is_reconnecting = False
        self.grab_timeout_ms = 500
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
                        time.sleep(1)
                        continue
                    
                    # Create and open camera with the first device
                    self.camera = pylon.InstantCamera(tl_factory.CreateDevice(devices[0]))
                    self.camera.Open()
                    
                    # Configure format converter
                    self.converter = pylon.ImageFormatConverter()
                    self.converter.OutputPixelFormat = pylon.PixelType_RGB8packed
                    self.converter.OutputBitAlignment = pylon.OutputBitAlignment_MsbAligned

                    # Create and register image handler
                    self.image_handler = PylonImageHandler()
                    self.camera.RegisterImageEventHandler(self.image_handler, 
                                                 pylon.RegistrationMode_Append,
                                                 pylon.Cleanup_Delete)

                    # Device info
                    model_name = self.camera.GetDeviceInfo().GetModelName()
                    camera_ip = self.camera.GetDeviceInfo().GetIpAddress()
                    logger.info(f"##### Pylon camera connected: {model_name} ({camera_ip}) #####")
                    
                    # Start grabbing with latest image only strategy
                    self.camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
                    self.consecutive_failures = 0
                    
                    # Start the acquisition loop in continuous mode
                    success = True
                    break
                    
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
        
    def get_frame(self):
        """
        Get the latest frame from the image handler.
        If no new frame is available, trigger the retrieval of a new one.
        Returns a grayscale frame for consistency with the rest of the application.
        """
        if not self.camera or not self.camera.IsGrabbing() or not self.image_handler:
            logger.error("Camera is not initialized or not grabbing")
            return None
            
        # Try to get the last image from the handler
        frame = self.image_handler.get_last_image()
        
        # If no frame is available, manually trigger a retrieval
        if frame is None:
            try:
                # Get a new grab result (this will call OnImageGrabbed in the handler)
                grabResult = self.camera.RetrieveResult(self.grab_timeout_ms, pylon.TimeoutHandling_Return)
                if grabResult and grabResult.IsValid():
                    grabResult.Release()  # Release the result as it's handled by the event handler
                    # Try to get the image again after the event handler has processed it
                    frame = self.image_handler.get_last_image()
                else:
                    if grabResult:
                        grabResult.Release()
            except Exception as e:
                logger.warning(f"Error retrieving frame: {e}")
        
        # Process the frame if available
        if frame is not None:
            self.consecutive_failures = 0
            
            # Convert to grayscale if the frame is color
            if len(frame.shape) == 3 and frame.shape[2] == 3:
                frame = cv.cvtColor(frame, cv.COLOR_RGB2GRAY)
                
            return frame
        else:
            self.consecutive_failures += 1
            
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
        self.image_handler = None

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

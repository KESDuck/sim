from PyQt5.QtCore import QObject, pyqtSignal, QTimer
import numpy as np
import time
import yaml

from utils.logger_config import get_logger
from utils.tools import map_image_to_robot, save_image, draw_cross, draw_points, add_border
from models.robot_model import RobotModel
from models.vision_model import VisionModel

logger = get_logger("Controller")
with open('config.yml', 'r') as file:
    config = yaml.safe_load(file)


class CrossPositionManager:
    """
    Manages the position of the cross overlay on camera frames.
    """
    def __init__(self, homo_matrix):
        self.cam_xy = np.array([1.0, 1.0], dtype=np.float64)
        self.robot_xy = None
        self.homo_matrix = homo_matrix

    def shift(self, dx=0, dy=0):
        """Move cross in camera position by delta x,y."""
        x, y = self.cam_xy
        self.set_position(x+dx, y+dy)
        
    def set_position(self, x, y):
        """Set the cross position in camera coordinates."""
        self.cam_xy = np.array([float(x), float(y)], dtype=np.float64)
        self.robot_xy = map_image_to_robot(self.cam_xy, self.homo_matrix)
        
    def get_position_info(self):
        """Get formatted position information for display."""
        cam_x, cam_y = self.cam_xy
        if self.robot_xy is None:
            return f"Camera: ({cam_x:.1f}, {cam_y:.1f}), Robot: (N/A)"
        else:
            robot_x, robot_y = self.robot_xy
            return f"Camera: ({cam_x:.1f}, {cam_y:.1f}), Robot: ({robot_x:.2f}, {robot_y:.2f})"

class CentroidManager:
    """
    Manages centroid processing operations: sorting, filtering, and converting.
    """
    def __init__(self, homo_matrix):
        self.homo_matrix = homo_matrix
        self.raw_centroids = None  # used by _prepare_and_emit_frame
        self.processed_centroids = None  # used by _update_centroids
        self.last_processed_time = None  # Timestamp when processing last completed

    def process_centroids(self, centroids):
        """
        Process centroids for robot use: 
        1. Sort centroids
        2. Convert to robot coordinates if needed
        3. Filter
        
        Args:
            centroids (list): List of (x, y) coordinates
            
        Returns:
            list: Processed centroids ready for robot use
        """
        # Store the raw centroids
        self.raw_centroids = centroids
        
        if centroids is None or len(centroids) == 0:
            self.processed_centroids = []
            return []
            
        # Sort centroids
        sorted_centroids = self.sort_centroids(centroids)
        
        # Convert to robot coordinates if needed
        robot_centroids = self.convert_to_robot_coords(sorted_centroids)
        
        # Store processed centroids
        self.processed_centroids = robot_centroids
        
        # Store timestamp when processing completed
        self.last_processed_time = time.time()
        
        return robot_centroids

    def is_centroid_updated_recently(self):
        """Check if centroid processing was done recently."""
        if self.last_processed_time is None:
            return False
        return time.time() - self.last_processed_time < 1.0  # 1 second threshold

    def sort_centroids(self, centroids, x_tolerance=30):
        """
        Sort centroids such that they are grouped by similar x-coordinates,
        and within each group sorted by y-coordinates.

        Args:
            centroids (list): List of (x, y) centroid coordinates
            x_tolerance (int, optional): Maximum difference in x-coordinates for grouping

        Returns:
            list: A flat list of centroids, sorted by grouped x and then y
        """
        if len(centroids) == 0:
            return []
            
        # Step 1: Sort by x-coordinates first
        sorted_centroids = sorted(centroids, key=lambda c: c[0])

        # Step 2: Group centroids into clusters based on x_tolerance
        groups = []
        current_group = [sorted_centroids[0]]

        for i in range(1, len(sorted_centroids)):
            if abs(sorted_centroids[i][0] - current_group[-1][0]) <= x_tolerance:
                current_group.append(sorted_centroids[i])
            else:
                groups.append(sorted(current_group, key=lambda c: c[1]))  # Sort group by y
                current_group = [sorted_centroids[i]]

        groups.append(sorted(current_group, key=lambda c: c[1]))  # Sort last group

        # Step 3: Flatten list
        return [c for group in groups for c in group]
    
    def convert_to_robot_coords(self, centroids):
        """
        Convert camera coordinates to robot coordinates using homography matrix.
        
        Args:
            centroids (list): List of (x, y) camera coordinates
            
        Returns:
            list: List of (x, y) robot coordinates
        """
        if not centroids:
            return []
            
        return [map_image_to_robot(point, self.homo_matrix) for point in centroids]


class AppController(QObject):
    """
    Controller that coordinates between models and views.
    Manages centroids selection, robot positioning, camera frame capture, and processing flow.
    """
    # Signals for communicating with the view
    cell_index_changed = pyqtSignal(int)
    cell_max_changed = pyqtSignal(int)
    frame_updated = pyqtSignal(object)  # Signal to send frames to the view
    status_message = pyqtSignal(str)    # Signal for status messages
    robot_status_message = pyqtSignal(str)  # Signal for robot status messages

    def __init__(self):
        super().__init__()
        self.robot = RobotModel(ip=config["robot"]["ip"], port=config["robot"]["port"])
        self.vision = VisionModel(cam_type=config["cam_type"])
        
        # Connect robot signals
        self.robot.robot_connected.connect(self._on_robot_connected)
        self.robot.robot_connection_error.connect(self._on_robot_error)
        self.robot.robot_status.connect(self._on_robot_status)
        
        # Initialize managers
        self.homo_matrix = config["homo_matrix"]
        self.cross_manager = CrossPositionManager(self.homo_matrix)
        self.centroid_manager = CentroidManager(self.homo_matrix)
        
        # keep track if it is batch inserting 
        self.pause_insert = False

        # TODO: this determines screw boundaries
        self.capture_position_idx = 0
        self.conveyor_position_idx = 0

        self.capture_positions = config["capture_positions"]

        # QTimer to update frames
        self.update_frame_timer = QTimer(self)
        self.update_frame_timer.timeout.connect(self.update_frame)
        self.update_frame_timer.start(200)

        # Current view state (live/paused/etc.)
        self.current_view_state = "paused orig"
        
        # Current active tab ("Engineer" or "User")
        self.current_tab = "Engineer"
        
        # List to store cross positions
        self.cross_positions = []
        
        # Emit initial status message
        self.status_message.emit("Press R Key to note current cross position")
        
        # Connect to vision model's signals - do this last after all methods are defined
        self.vision.frame_processed.connect(self.on_frame_processed)
        self.vision.live_worker.frame_ready.connect(self.on_live_frame_ready)
        self.vision.live_worker.error_occurred.connect(self.on_camera_error)

    def _on_robot_connected(self):
        """Handle successful robot connection."""
        logger.info("Robot connected successfully")
        self.status_message.emit("Robot connected")
        
    def _on_robot_error(self, error_msg):
        """Handle robot connection error."""
        logger.error(f"Robot connection error: {error_msg}")
        self.status_message.emit(f"Robot connection error: {error_msg}, try reconnect button")

    def _on_robot_status(self, status_message):
        """Handle robot status messages."""
        self.robot_status_message.emit(status_message)

    def on_frame_processed(self, success):
        """Handle completion of frame processing from the vision model"""
        if success:
            # Update centroids data
            self._update_centroids()
            
            # Get the processed frame based on current view state
            frame = self.get_frame_for_display(self.current_view_state)
            self._prepare_and_emit_frame(frame)
        else:
            logger.error("Process image failure")
            self.status_message.emit("Process image failure")
            
    def on_live_frame_ready(self, frame):
        """Handle live frame updates from the vision thread"""
        if self.current_view_state == "live" and self.current_tab == "Engineer":
            # Store the frame and emit it
            self.vision.frame_camera_live = frame
            self._prepare_and_emit_frame(frame, draw_cells=False)

    def _prepare_and_emit_frame(self, frame, draw_cells=True):
        """Helper method to prepare a frame with overlays and emit it."""
        if frame is None:
            return
            
        # Make a copy to avoid modifying the original
        frame = frame.copy()
        
        # Add overlay with centroids if available and requested
        if draw_cells and self.current_view_state != "live" and self.centroid_manager.raw_centroids is not None:
            frame = draw_points(
                frame, 
                self.centroid_manager.raw_centroids, 
                -1,  # No current index 
                size=10
            )
        
        # Draw cross on frame before emitting
        cross_x, cross_y = self.cross_manager.cam_xy
        frame = draw_cross(frame, cross_x, cross_y)
        
        # Add 1px border
        frame = add_border(frame, color=(0, 0, 0), thickness=1)
        
        # Emit the prepared frame
        self.frame_updated.emit(frame)

    def set_view_state(self, state):
        """Update the current view state."""
        previous_state = self.current_view_state
        self.current_view_state = state
        logger.info(f"View state changed to: {state}")
        
        # Adjust frame timer based on view state
        if state == "live" and self.current_tab == "Engineer":
            # For live view, start the timer and use the background thread
            if not self.update_frame_timer.isActive():
                self.update_frame_timer.start(200)
            self.vision.live_capture()
        else:
            # For non-live states, stop the timer and live capture
            if self.update_frame_timer.isActive():
                self.update_frame_timer.stop()
            self.vision.stop_live_capture()
            
            # If we're switching from live to paused and we don't have a stored frame,
            # capture one first
            if previous_state == "live" and self.vision.frame_camera_stored is None:
                logger.info("Capturing a frame before switching to paused state")
                self.vision.capture_and_process()
            
            # Emit the appropriate frame for this state
            frame = self.get_frame_for_display(state)
            self._prepare_and_emit_frame(frame)

    def _update_centroids(self):
        """Helper method to update centroids data from the vision model."""
        # Get centroids from vision and store them in centroid manager
        _centroids = self.centroid_manager.process_centroids(self.vision.centroids)
        self.cell_max_changed.emit(len(_centroids) - 1 if len(_centroids) > 0 else 0)
        
    def update_frame(self):
        """Process frame when requested (e.g., via Process button)."""
        # Get the current state
        # logger.info(f"Updating frame in state: {self.current_view_state}")
        
        if self.current_view_state == "live":
            # For live mode, just ensure live capture is running
            # The frame updates will come through the signal handler
            self.vision.live_capture()
        else:
            # This is a manual capture request (Process button was clicked)
            # Make sure live capture is stopped
            self.vision.stop_live_capture()
            
            # Capture and process a new frame
            # logger.info("Processing new frame on request")
            if self.vision.capture_and_process():
                # If successful, update the displayed frame
                frame = self.get_frame_for_display(self.current_view_state)
                self._prepare_and_emit_frame(frame)

    def process_section(self, section_id, capture_only=False) -> bool:
        """
            capture and process a section
            - I. move robot (and conveyor) to section_id
            - II. capture and process image
            - III. queue positions to robot 
            - IV. robot start inserting
        """

        if not self.robot.is_connected:
            logger.error(f"Robot is not connected")
            return False
        
        if self.robot.robot_state != RobotModel.IDLE:
            logger.error(f"Robot not in IDLE state")
            return False
        
        ##### I #####
        # Get capture position for this section
        x, y, z, u = self.capture_positions[section_id]
        
        # Move robot to capture position
        if not self.robot.capture(x, y, z, u):
            logger.error(f"Failed to send robot to capture position")
            return False
        
        # Wait until robot is at capture position
        while self.robot.app_state != RobotModel.IDLE:
            time.sleep(0.1)
        
        ##### II #####
        # Stop live capture if running
        self.vision.stop_live_capture()
        
        # Longer pause to make sure robot is not shaking
        time.sleep(0.5)
        
        # Capture and process frame, with 3 retries
        # Vision model will emit frame_processed signal that will update centroids
        # update centroids will sort, filter, and convert centroids to robot coordinates
        for i in range(3):
            if self.vision.capture_and_process():
                break
            else:
                logger.error(f"Failed to capture, retrying...")
                time.sleep(0.5)
        else:
            logger.error(f"Failed to capture section {section_id}")
            return False

        # sanity check that centroid is updated recently
        if not self.centroid_manager.is_centroid_updated_recently():
            logger.error(f"Centroid not updated recently")
            return False

        if capture_only:
            return True
        
        ##### III, IV #####

        # Pause to make sure state is IDLE
        time.sleep(1.0)

        # Send queue, robot state will be in INSERTING unless stopped or queue finished
        if not self.robot.queue_points(self.centroid_manager.processed_centroids):
            return False

        return True

    
    def stop_insert(self):
        """Connect stop button with robot stop"""
        pass

    def save_current_frame(self):
        if self.vision.frame_camera_stored is not None and self.vision.frame_camera_stored.size > 0:
            save_image(self.vision.frame_camera_stored, config["save_folder"])
            self.status_message.emit("Frame saved")
        else:
            logger.warning("No frame stored to save.")

    def shift_cross(self, dx=0, dy=0):
        """
        Move cross position by delta x,y or set to absolute position.
        If both dx and dy are provided as non-zero/non-None values,
        they are treated as absolute coordinates.
        """
        # Get current position
        current_x, current_y = self.cross_manager.cam_xy
        
        # Determine if this is relative movement or absolute positioning
        if dx != 0 and dy != 0:
            # Both non-zero - treat as absolute coordinates
            new_x, new_y = dx, dy
        else:
            # Treat as relative movement
            new_x = current_x + dx
            new_y = current_y + dy
        
        # Update cross position
        self.cross_manager.set_position(new_x, new_y)
        
        # Get position info including robot coordinates
        position_info = self.cross_manager.get_position_info()
        
        # Emit status message
        log_msg = f"Cross position updated: {position_info}"
        logger.info(log_msg)
        self.status_message.emit(log_msg)
        
        # Emit an updated frame with the new cross position
        frame = self.get_frame_for_display(self.current_view_state)
        self._prepare_and_emit_frame(frame)
        
    def get_frame_for_display(self, view_state):
        """Get appropriate frame based on view state."""
        if view_state == "live":
            return self.vision.frame_camera_live
        elif view_state == "paused orig":
            return self.vision.frame_camera_stored
        elif view_state == "paused thres":
            return self.vision.frame_threshold
        elif view_state == "paused contours":
            return self.vision.frame_contour
        else:
            logger.error(f"Bad view state: {view_state}")
            return None

    def live_capture(self):
        return self.vision.live_capture()

    def close(self):
        """Clean up resources"""
        self.robot.close()
        self.vision.close()

    def set_current_tab(self, tab_name):
        """Set the current active tab."""
        self.current_tab = tab_name
        logger.info(f"Active tab changed to: {tab_name}")
        
        # If changing tabs, update frame timer state and live camera state
        if self.current_view_state == "live":
            if tab_name == "Engineer":
                if not self.update_frame_timer.isActive():
                    self.update_frame_timer.start(200)
                # Enable live camera in Engineer tab with live view
                self.vision.live_capture()
            else:
                if self.update_frame_timer.isActive():
                    self.update_frame_timer.stop()
                # Disable live camera in other tabs
                self.vision.stop_live_capture()
                # Emit a single frame for the current state
                frame = self.get_frame_for_display(self.current_view_state)
                self._prepare_and_emit_frame(frame)
        else:
            # For non-live states, always ensure live camera is stopped
            self.vision.stop_live_capture()

    def handle_r_key(self):
        """Handle R key press to record cross position"""
        x, y = self.cross_manager.cam_xy
        self.cross_positions.append([x, y])
        position_number = len(self.cross_positions)
        msg = f"#{position_number} [{x}, {y}]"
        logger.info(msg)
        self.status_message.emit(msg)

    def reconnect_camera(self):
        """Manually reconnect the camera"""
        self.status_message.emit("Reconnecting camera...")
        
        # Stop all camera operations
        if self.update_frame_timer.isActive():
            self.update_frame_timer.stop()
        self.vision.stop_live_capture()
        
        # Perform reconnection
        success = self.vision.camera.reconnect()
        
        # Resume previous state if successful
        if success:
            self.status_message.emit("Camera reconnected")
            if self.current_view_state == "live":
                self.update_frame_timer.start(200)
                self.vision.live_capture()
        else:
            self.status_message.emit("Reconnection failed")
            
        return success

    def on_camera_error(self, error_message):
        """Handle camera error messages from the worker thread"""
        logger.error(f"Camera error: {error_message}")
        self.status_message.emit(error_message) 
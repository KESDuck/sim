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
        self.img_raw_centroids = []
        self.img_sorted_centroids = []
        self.img_filtered_centroids = []   # used by _prepare_and_emit_frame
        self.robot_centroids = []

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
        if centroids is None or len(centroids) == 0:
            self.img_raw_centroids = []
            self.img_sorted_centroids = []
            self.img_filtered_centroids = []   # used by _prepare_and_emit_frame
            self.robot_centroids = []
            return []
        
        # Store the raw centroids
        self.img_raw_centroids = centroids
            
        # Sort centroids
        self.img_sorted_centroids = self.sort_centroids(centroids)

        # Filter centroids to keep only those within boundary
        self.img_filtered_centroids = self.filter_centroids(self.img_sorted_centroids)

        # tmp
        self.img_filtered_centroids = self.filter_test_centroids(self.img_filtered_centroids)
        self.img_filtered_centroids = self.img_filtered_centroids[:10] if len(self.img_filtered_centroids) > 10 else self.img_filtered_centroids

        # Convert to robot coordinates if needed
        self.robot_centroids = self.convert_to_robot_coords(self.img_filtered_centroids)
                
        # Store timestamp when processing completed
        self.last_processed_time = time.time()
        
        return self.robot_centroids

    def filter_centroids(self, centroids):
        """
        Filter centroids to keep only those within configured boundary.
        
        Args:
            centroids (list): List of (x, y) coordinates
            
        Returns:
            list: Filtered list of centroids within boundary
        """
        if not centroids:
            return []
        
        # Get boundary values from config
        x_min = config["boundary"]["x_min"]
        x_max = config["boundary"]["x_max"]
        y_min = config["boundary"]["y_min"]
        y_max = config["boundary"]["y_max"]
        
        # Filter centroids
        return [point for point in centroids 
                if x_min < point[0] < x_max and y_min < point[1] < y_max]
    
    def filter_test_centroids(self, centroids):
        """
        Select 9 centroids evenly distributed in a 3x3 grid.
        
        Args:
            centroids (list): List of (x, y) coordinates
            
        Returns:
            list: List of 9 evenly distributed centroids
        """
        if not centroids or len(centroids) < 9:
            return centroids  # Return all if less than 9
        
        # Get boundary values from config
        x_min = config["boundary"]["x_min"]
        x_max = config["boundary"]["x_max"]
        y_min = config["boundary"]["y_min"]
        y_max = config["boundary"]["y_max"]
        
        # Define 3x3 grid cells
        x_step = (x_max - x_min) / 3
        y_step = (y_max - y_min) / 3
        
        selected_centroids = []
        
        # For each grid cell, find closest centroid to cell center
        for i in range(3):
            for j in range(3):
                # Calculate cell center
                cell_center_x = x_min + (i + 0.5) * x_step
                cell_center_y = y_min + (j + 0.5) * y_step
                
                # Find centroid closest to this cell center
                min_distance = float('inf')
                closest_centroid = None
                
                for centroid in centroids:
                    # Check if centroid is in this cell
                    if (x_min + i * x_step <= centroid[0] <= x_min + (i + 1) * x_step and
                        y_min + j * y_step <= centroid[1] <= y_min + (j + 1) * y_step):
                        
                        # Calculate distance to cell center
                        dist = ((centroid[0] - cell_center_x) ** 2 + 
                                (centroid[1] - cell_center_y) ** 2) ** 0.5
                        
                        if dist < min_distance:
                            min_distance = dist
                            closest_centroid = centroid
                
                # If found a centroid in this cell, add it
                if closest_centroid:
                    selected_centroids.append(closest_centroid)
        
        return selected_centroids

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

        # Process note
        self._insertion_routine = False
        
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
        # logger.error(f"Robot connection error: {error_msg}")
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
        if draw_cells and self.current_view_state != "live" and self.centroid_manager.img_filtered_centroids is not None:
            frame = draw_points(
                frame, 
                self.centroid_manager.img_filtered_centroids, 
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

    def process_section(self, section_id, capture_only=True):
        """Non-blocking implementation of process_section using signals/slots"""
        self._insertion_routine = True

        # Check preconditions
        if not self.robot.is_connected:
            self.status_message.emit("Robot not connected")
            self._insertion_routine = False
            return False
        
        if self.robot.robot_state != RobotModel.IDLE:
            self.status_message.emit("Robot not in IDLE state")
            self._insertion_routine = False
            return False
        
        logger.info(f"PHASE I - button pressed -> robot move to capture position")

        # Step 1: Move robot to capture position
        x, y, z, u = self.capture_positions[section_id]
        self.robot.capture(x, y, z, u)
        
        # Connect to the robot's state change signal to trigger next step
        # This is one-time connection that disconnects after execution
        self.robot.robot_op_state_changed.connect(self._on_robot_at_capture_position)
            
    def _on_robot_at_capture_position(self, state):
        """Called when robot reaches capture position"""
        # Disconnect from signal to prevent multiple calls
        self.robot.robot_op_state_changed.disconnect(self._on_robot_at_capture_position)

        if not self._insertion_routine:
            logger.error("(_on_robot_at_capture_position) Not in insertion routine")
            return

        logger.info(f"PHASE II - robot at capture position -> wait 1000ms to stabilize")

        if state != RobotModel.IDLE:
            logger.error(f"Robot not in idle after moving to capture, current state: {state}")
            self._insertion_routine = False
            return  # Not the state we're waiting for
        
        # Pause briefly to stabilize
        QTimer.singleShot(1000, self._capture_and_process_image)
        
    def _capture_and_process_image(self):
        """Capture and process image after robot is in position"""
        if not self._insertion_routine:
            logger.error("(_capture_and_process_image) Not in insertion routine")
            return
        
        logger.info(f"PHASE III - waited 1000ms -> camera capture -> wait 500ms")

        self.vision.stop_live_capture()
        
        # Capture image and connect to frame_processed signal
        for i in range(3):
            if self.vision.capture_and_process():
                if self.centroid_manager.is_centroid_updated_recently():
                    # TODO: return if capture only
                    QTimer.singleShot(500, self._queue_points_to_robot)
                else:
                    self._insertion_routine = False
                    logger.error(f"Centroid not updated recently, please check code")
                    time.sleep(0.5)
                break
            else:
                logger.warning(f"Failed to capture image, retrying...")
                # TODO: avoid busy wait
                time.sleep(0.5)
        else:
            self._insertion_routine = False
            self.status_message.emit("Failed to capture image after multiple retries")
        
    def _queue_points_to_robot(self):
        """Send processed centroids to robot"""
        if not self._insertion_routine:
            logger.error("(_queue_points_to_robot) Not in insertion routine")
            return
        
        logger.info(f"PHASE IV - waited 500ms -> send queue to robot")

        if self.robot.robot_op_state != RobotModel.IDLE:
            logger.error("Robot not in idle for some weird reason")
            self._insertion_routine = False
            return  # Not the state we're waiting for

        # Queue points and connect to completion signal
        if self.robot.queue_points(self.centroid_manager.robot_centroids):
            # Connect to robot state change to detect completion
            self.robot.robot_op_state_changed.connect(self._on_robot_insertion_complete)
        else:
            logger.error("Failed to send queue")
            self._insertion_routine = False
        
    def _on_robot_insertion_complete(self, state):
        """Called when robot completes insertion task or stopped"""
        self.robot.robot_op_state_changed.disconnect(self._on_robot_insertion_complete)

        if not self._insertion_routine:
            logger.error("(_on_robot_insertion_complete) Not in insertion routine")
            return
        
        logger.info(f"PHASE V - insertion completed")

        if state == RobotModel.IDLE:
            
            
            self.status_message.emit("Insertion complete")
        else:
            logger.error("Robot not in idle for some weird reason")

        self._insertion_routine = False

    
    def stop_insert(self):
        """Connect stop button with robot stop"""
        self.robot.stop()

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
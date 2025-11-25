from PyQt5.QtCore import QObject, pyqtSignal, QTimer
import numpy as np
import time
import yaml

from utils.logger_config import get_logger
from utils.tools import map_image_to_robot, save_image, draw_cross, draw_points, add_border, draw_boundary_box
from utils.centroid import Centroid, CentroidManager
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


class AppController(QObject):
    """
    Controller that coordinates between UI, robot, and vision.
    Manages centroids selection, robot positioning, camera frame capture, and processing flow.
    """
    # Signals
    cell_index_changed = pyqtSignal(int)
    cell_max_changed = pyqtSignal(int)
    frame_updated = pyqtSignal(object)
    status_message = pyqtSignal(str)
    robot_status_message = pyqtSignal(str)
    section_changed = pyqtSignal(str)
    position_updated = pyqtSignal(float, float, float, float)  # img_x, img_y, robot_x, robot_y
    state_mode_updated = pyqtSignal(str, str)  # state, mode

    # State machine states
    STATE_IDLE = "IDLE"
    STATE_MOVE_TO_CAPTURE = "MOVING_CAPTURE"
    STATE_CAPTURING = "CAPTURING"
    STATE_MOVE_TO_RELOAD = "MOVING_RELOAD"
    STATE_QUEUEING = "QUEUEING"
    STATE_LOADING_MAGAZINE = "LOADING_MAGAZINE"
    STATE_INSERTING = "INSERTING"
    STATE_TESTING = "TESTING"

    # State machine modes
    MODE_IDLE = "IDLE MODE"
    MODE_INSERT = "INSERT MODE"
    MODE_TEST = "TEST MODE"
    MODE_CAPTURE = "CAPTURE MODE"

    # expected responses
    EXPECT_POSITION_REACHED = "POSITION_REACHED"
    EXPECT_QUEUE_APPENDED = "QUEUE_APPENDED"
    EXPECT_QUEUE_CLEARED = "QUEUE_CLEARED"
    EXPECT_INSERT_DONE = "INSERT_DONE"
    EXPECT_TEST_DONE = "TEST_DONE"
    EXPECT_STOPPED = "STOPPED"
    EXPECT_MAGAZINE_LOADED = "MAGAZINE_LOADED"
    
    # batch processing constants
    QUEUE_BATCH_SIZE = 15

    current_display_section = "5"

    def __init__(self):
        super().__init__()
        
        # Initialize models
        self._init_models()
        
        # Initialize UI state
        self._init_ui_state()
        
        # Initialize state machine state
        self._init_state_machine()
        
        # Connect signals
        self._connect_signals()

        self.robot.connect_to_server()
        
        # Ensure UI is synchronized with initial section
        self.section_changed.emit(self.current_display_section)
        
        # Emit initial state/mode
        self.state_mode_updated.emit(self.current_operation_state, self.current_operation_mode)
    
    # ===== Initialization Methods =====
    
    def _init_models(self):
        """Initialize robot and vision models"""
        self.robot = RobotModel(
            ip=config["robot"]["ip"], 
            port=config["robot"]["port"],
            simulated=config["robot"].get("simulated", False)
        )
        self.vision = VisionModel(cam_type=config["cam_type"])
        
        # Initialize managers
        self.homo_matrix = config["homo_matrix"]
        self.cross_manager = CrossPositionManager(self.homo_matrix)
        self.centroid_manager = CentroidManager(self.homo_matrix)
        
        # Section configurations (renamed from capture_positions to use section_config)
        self.section_config = config["section_config"]
    
    def _init_ui_state(self):
        """Initialize UI state variables"""
        # Current view state (live/paused/etc.)
        self.current_view_state = "paused orig"
        
        # Current active tab
        self.current_tab = "Engineer"
        
        # List to store cross positions
        self.cross_positions = []
        
        # Store last displayed frame for saving
        self.last_displayed_frame = None
    
    def _init_state_machine(self):
        """Initialize state machine variables"""
        self.current_operation_state = self.STATE_IDLE
        self.current_operation_mode = self.MODE_IDLE
        self.operation_section_id = None
    
    def _connect_signals(self):
        """Connect signals between components"""
        # Connect robot signals
        self.robot.robot_connected.connect(self._on_robot_connected)
        self.robot.robot_connection_error.connect(self._on_robot_error)
        self.robot.robot_status.connect(self._on_robot_status)
        self.robot.error.connect(self._on_robot_error)
        
        # Connect vision signals
        self.vision.frame_processed.connect(self._on_frame_processed)
        
        # Initial status message
        self.status_message.emit("Press R Key to note current cross position")
    
    # ===== Signal Handlers =====
    
    def _on_robot_connected(self):
        """Handle successful robot connection."""
        logger.info("Robot connected successfully")
        self.status_message.emit("Robot connected")
        
    def _on_robot_error(self, error_msg):
        """Handle robot connection error."""
        self.status_message.emit(f"Robot error: {error_msg}")

    def _on_robot_status(self, status_message):
        """Handle robot status messages."""
        self.robot_status_message.emit(status_message)
    
    def _on_frame_processed(self, success):
        """Process centroids after capture and process"""
        if success:
            self._update_centroids()
            frame = self._get_frame_for_display(self.current_view_state)
            self._prepare_and_emit_frame(frame)
        else:
            logger.error("Process image failure")
            self.status_message.emit("Process image failure")
    
    # ===== Frame Handling Methods =====
    
    # def capture_process_frame(self):
    #     """Process frame when requested (e.g., via Process button)."""
    #     if self.current_view_state == "live":
    #         # In live mode, we're already capturing frames through the live_worker thread
    #         # Just ensure the live capture is running
    #         self.vision.live_capture()
    #     else:
    #         # For non-live states, stop live capture and get a single frame
    #         self.vision.stop_live_capture()
    #         self.vision.capture_and_process()
    
    def _prepare_and_emit_frame(self, frame, draw_cells=True):
        """Draw cells and cross on frame then emit"""
        if frame is None:
            return
            
        # Make a copy to avoid modifying the original
        frame = frame.copy()
        
        # Draw bounding boxes from current section config
        current_section = self.section_config.get(self.current_display_section, {})
        bounding_boxes = current_section.get("bounding_boxes", [])
        frame = draw_boundary_box(frame, bounding_boxes)
        
        # Add overlay with centroids if available and requested
        if draw_cells and self.centroid_manager.centroids is not None:
            frame = draw_points(
                frame, 
                self.centroid_manager.centroids, 
                -1,  # No current index 
                size=5,
                row_indices=self.centroid_manager._row_indices
            )
        
        # Draw cross on frame before emitting
        cross_x, cross_y = self.cross_manager.cam_xy
        frame = draw_cross(frame, cross_x, cross_y)
        
        # Add 1px border
        frame = add_border(frame, color=(0, 0, 0), thickness=1)
        
        # Store the prepared frame for saving
        self.last_displayed_frame = frame.copy()
        
        # Emit the prepared frame
        self.frame_updated.emit(frame)
    
    def _get_frame_for_display(self, view_state):
        """Get appropriate frame based on view state."""
        if view_state == "paused orig":
            return self.vision.frame_camera_stored
        elif view_state == "paused thres":
            return self.vision.frame_threshold
        elif view_state == "paused contours":
            return self.vision.frame_contour
        else:
            logger.error(f"Bad view state: {view_state}")
            return None
    
    def _update_centroids(self):
        """Helper method to update centroids data from the vision model."""
        # Get bounding boxes from current section
        current_section = self.section_config.get(self.current_display_section, {})
        bounding_boxes = current_section.get("bounding_boxes", [])
        
        _centroids = self.centroid_manager.process_centroids(self.vision.centroids, bounding_boxes)
        self.cell_max_changed.emit(len(_centroids) - 1 if len(_centroids) > 0 else 0)
    
    # ===== UI Control Methods =====
    
    def set_view_state(self, state):
        """Update the current view state: paused orig, paused thres, paused contours."""
        previous_state = self.current_view_state
        self.current_view_state = state
        logger.info(f"View state changed to: {state}")
        
        # Get frame for display
        frame = self._get_frame_for_display(state)
        self._prepare_and_emit_frame(frame)

    def set_current_tab(self, tab_name):
        """Set the current active tab."""
        self.current_tab = tab_name
        logger.info(f"Active tab changed to: {tab_name}")
        
        # Emit a frame for the current state
        frame = self._get_frame_for_display(self.current_view_state)
        self._prepare_and_emit_frame(frame)

    def save_current_frame(self):
        """Save the current displayed frame (with overlays) to disk."""
        if self.last_displayed_frame is not None and self.last_displayed_frame.size > 0:
            save_image(self.last_displayed_frame, config["save_folder"])
            self.status_message.emit("Frame saved")
        else:
            logger.warning("No frame available to save.")

    def handle_r_key(self):
        """Handle R key press to record cross position"""
        x, y = self.cross_manager.cam_xy
        self.cross_positions.append([x, y])
        position_number = len(self.cross_positions)
        msg = f"#{position_number} [{x}, {y}]"
        logger.info(msg)
        self.status_message.emit(msg)

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
        cam_x, cam_y = self.cross_manager.cam_xy
        robot_x, robot_y = self.cross_manager.robot_xy if self.cross_manager.robot_xy is not None else (0.0, 0.0)
        
        # Emit position update signal
        self.position_updated.emit(float(cam_x), float(cam_y), float(robot_x), float(robot_y))
        
        # Emit status message
        log_msg = f"Cross position updated: {position_info}"
        logger.info(log_msg)
        self.status_message.emit(log_msg)
        
        # Emit an updated frame with the new cross position
        frame = self._get_frame_for_display(self.current_view_state)
        self._prepare_and_emit_frame(frame)
        

    # ===== State Machine Methods =====
    
    def start_section_operation(self, section_id, mode):
        """Start a section operation (insert or test)"""
        if self.robot.robot_state == self.robot.DISCONNECT:
            logger.warning("Robot not connected")
            return False
            
        if self.current_operation_state != self.STATE_IDLE:
            logger.error(f"Cannot start operation: current state is {self.current_operation_state}")
            return False
            
        # Set operation parameters
        logger.info(f"Starting mode: {mode}")
        self.operation_section_id = section_id
        self.current_operation_mode = mode
        
        # Start the state machine
        self.transition_to(self.STATE_MOVE_TO_CAPTURE)
        return True
    
    def transition_to(self, new_state, reason="success"):
        """
        Transition state machine to a new state
        
        Args:
            new_state: The target state to transition to
            reason: Reason for transition ("success", "timeout", "error", "failure")
        """
        logger.info(f"Operation state transition: {self.current_operation_state} ➡️ {new_state} (reason: {reason})")
        
        # If we're stopping, don't allow transitions to non-idle states
        if hasattr(self, 'stopping') and self.stopping and new_state != self.STATE_IDLE:
            logger.info("Stop requested, ignoring transition to non-idle state")
            return
            
        self.current_operation_state = new_state
        
        # Emit state/mode update signal
        self.state_mode_updated.emit(self.current_operation_state, self.current_operation_mode)
        
        # Execute state entry action
        if new_state == self.STATE_MOVE_TO_CAPTURE:
            self._execute_move_capture()
        elif new_state == self.STATE_CAPTURING:
            self.execute_capture()
        elif new_state == self.STATE_MOVE_TO_RELOAD:
            self._execute_move_reload()
        elif new_state == self.STATE_QUEUEING:
            self._execute_queue()
        elif new_state == self.STATE_LOADING_MAGAZINE:
            self._execute_load_magazine()
        elif new_state == self.STATE_INSERTING:
            self._execute_insert()
        elif new_state == self.STATE_TESTING:
            self._execute_test()
        elif new_state == self.STATE_IDLE:
            self.current_operation_mode = self.MODE_IDLE
    
    def _execute_move_capture(self):
        """Execute the move to capture position"""
        # Get section position
        try:
            x, y, z, u = self.get_section(self.operation_section_id)
            self.robot.send(
                cmd=f"move {x} {y} {z} {u}",
                expect=self.EXPECT_POSITION_REACHED,
                timeout=5.0,
                on_success=lambda: self.transition_to(self.STATE_CAPTURING),
                on_timeout=lambda: self.transition_to(self.STATE_IDLE, "timeout")
            )
        except Exception as e:
            logger.error(f"Move failed: {e}")
            self.transition_to(self.STATE_IDLE, "error")
            
    def execute_capture(self, no_robot=False):
        """Execute the capture operation
        
        Args:
            no_robot (bool): If True, skip state transitions and robot operations
        """
        
        # Try to capture and process image
        for i in range(3):
            if self.vision.capture_and_process():
                if self.centroid_manager.is_centroid_updated_recently():
                    if not no_robot:
                        self.centroid_manager.row_counter = 0
                        time.sleep(1)
                        self.transition_to(self.STATE_MOVE_TO_RELOAD)
                    return
                else:
                    logger.error("Centroid not updated recently")
                    time.sleep(0.5) # TODO: blocking call, should be non-blocking
            else:
                logger.warning(f"Failed to capture image, retrying... {i}")
                time.sleep(0.5) # TODO: blocking call, should be non-blocking
                
        # Failed after retries
        logger.error("Failed to capture after multiple attempts")
        self.status_message.emit("Failed to capture image")
        if not no_robot:
            self.transition_to(self.STATE_IDLE, "error")

    def _execute_move_reload(self):
        """Move the robot to reload position"""
        try:
            x, y, z, u = config["reload_position"]
            self.robot.send(
                cmd=f"move {x} {y} {z} {u}",
                expect=self.EXPECT_POSITION_REACHED,
                timeout=5.0,
                on_success=lambda: self.transition_to(
                    self.STATE_IDLE if self.current_operation_mode == self.MODE_CAPTURE else self.STATE_QUEUEING
                ),
                on_timeout=lambda: self.transition_to(self.STATE_IDLE, "timeout")
            )
        except Exception as e:
            logger.error(f"Move to reload position failed: {e}")
            self.transition_to(self.STATE_IDLE, "error")

    def _execute_queue(self):
        centroids = self.centroid_manager.centroids
        if not centroids:
            logger.error("No centroids available for queue")
            self.transition_to(self.STATE_IDLE, "error")
            return
        
        # Clear any existing queue first
        self.robot.send(
            cmd="clearqueue",
            expect=self.EXPECT_QUEUE_CLEARED,
            timeout=1.0,
            on_success=self._send_row,
            on_timeout=lambda: self.transition_to(self.STATE_IDLE, "timeout")
        )
    
    def _send_row(self):
        cur_row_counter = self.centroid_manager.row_counter

        if cur_row_counter >= self.centroid_manager.get_num_rows():
            # All rows sent and inserted, move to idle
            logger.info(f"Section completed 🎉")

            self.transition_to(
                self.STATE_IDLE
            )
            return
        
        # Check if current row has valid centroids
        if not self.centroid_manager.has_valid_centroids_in_row(cur_row_counter):
            # No valid centroids in current row, try next row
            logger.info(f"Row {cur_row_counter} has no valid centroids, skipping to next row")
            self.centroid_manager.next_row()
            
            # Check if we've run out of rows
            if self.centroid_manager.row_counter >= self.centroid_manager.get_num_rows():
                logger.info("All rows processed")
                self.transition_to(self.STATE_IDLE)
                return
        
        logger.info(f"Queue: row {cur_row_counter}")
        self._batch_send_centroids(self.centroid_manager.get_row(), 0)
    
    def _batch_send_centroids(self, centroids, start_idx):
        """
        Recursively send a batch of centroids to the robot.

        Args:
            centroids: List of Centroid objects
            start_idx: Index of the first centroid to send
        """
        if start_idx >= len(centroids):
            # All centroids of this row sent
            if self.current_operation_mode == self.MODE_INSERT:
                self.transition_to(self.STATE_LOADING_MAGAZINE)
            else:
                self.transition_to(self.STATE_TESTING)
            return
        
        end_idx = min(start_idx + self.QUEUE_BATCH_SIZE, len(centroids))
        batch = centroids[start_idx:end_idx]
        
        # Build the batch command
        queue_cmd = "queue " + " ".join([f"{centroid.robot_x:.2f} {centroid.robot_y:.2f}" for centroid in batch])
        
        logger.info(f"Queue batch {start_idx}-{end_idx-1}: Start")
        self.robot.send(
            cmd=queue_cmd,
            expect=self.EXPECT_QUEUE_APPENDED,
            timeout=1.0,
            on_success=lambda: self._batch_send_centroids(centroids, end_idx),
            on_timeout=lambda: self.transition_to(self.STATE_IDLE, "timeout")
        )

    def _execute_load_magazine(self):
        """Execute the magazine loading state"""
        centroids = self.centroid_manager.get_row()
        if not centroids:
            logger.error("No centroids available for magazine loading")
            self.transition_to(self.STATE_IDLE, "error")
            return
                
        num_screws = len(centroids)
        
        self.robot.send(
            cmd=f"loadmagazine {num_screws}",
            expect=self.EXPECT_MAGAZINE_LOADED,
            timeout=180.0,
            on_success=lambda: self.transition_to(self.STATE_INSERTING),
            on_timeout=lambda: self.transition_to(self.STATE_IDLE, "timeout")
        )

    def _execute_insert(self):
        """Execute the insertion state"""
        self.robot.send(
            cmd="insert",
            expect=self.EXPECT_INSERT_DONE,
            timeout=60.0,  # Use a reasonable timeout based on queue size
            on_success=lambda: self._on_row_complete(),
            on_timeout=lambda: self.transition_to(self.STATE_IDLE, "timeout")
        )

    def _execute_test(self):
        """Execute the testing state"""
        self.robot.send(
            cmd="test",
            expect=self.EXPECT_TEST_DONE,
            timeout=60.0,
            on_success=lambda: self._on_row_complete(),
            on_timeout=lambda: self.transition_to(self.STATE_IDLE, "timeout")
        )
    
    def _on_row_complete(self):
        """Called when a row has been fully processed (inserted or tested)"""
        self.centroid_manager.next_row()
        self.transition_to(self.STATE_QUEUEING)
    
    # ===== High-Level Operations =====
    
    def capture_section(self, section_id):
        """Start capture operation for given section"""
        return self.start_section_operation(section_id, self.MODE_CAPTURE)
    
    def insert_section(self, section_id):
        """Start insertion operation for given section"""
        return self.start_section_operation(section_id, self.MODE_INSERT)
    
    def test_section(self, section_id):
        """Start test operation for given section"""
        return self.start_section_operation(section_id, self.MODE_TEST)
    
    def get_section(self, section_id):
        """
        Get robot capture coordinates for a section. Handles both int and str section IDs
        to prevent type mismatch errors between UI (sends int) and config (uses str keys).
        
        Args:
            section_id: ID of the section to retrieve (1-9, can be int or str)
            
        Returns:
            Tuple of (x, y, z, u) coordinates from capture_position
        """
        # Convert to string to match section_config keys (fixes UI int vs config str mismatch)
        section_str = str(section_id)
        if section_str not in self.section_config:
            raise ValueError(f"Invalid section_id: {section_id}. Must be one of {list(self.section_config.keys())}")
        
        # Return capture_position from the section config
        return self.section_config[section_str]["capture_position"]
    
    def set_display_section(self, section_id):
        """
        Set the current section for display. Updates bounding boxes and centroid filtering.
        Emits section_changed signal for UI synchronization when section changes.
        """
        section_str = str(section_id)
        if section_str in self.section_config:
            old_section = self.current_display_section
            self.current_display_section = section_str
            
            # Emit signal for UI synchronization if section actually changed
            if old_section != section_str:
                self.section_changed.emit(section_str)
            
        else:
            logger.warning(f"Invalid section_id: {section_id}. Available sections: {list(self.section_config.keys())}")
    
    def change_speed(self, speed):
        """Change the robot speed"""
        logger.info(f"TODO IMPLEMENT THIS: Changing robot speed to {speed}")

        # self.robot.send(cmd=f"speed {speed}")

    def stop_all(self):
        """Stop the current robot operation"""
        logger.info("Stopping robot operation")
        
        # Clear any pending expectations to prevent delayed responses from causing state transitions
        self.robot.clear_expectations()
        
        self.robot.send(
            cmd="stop",
            expect=self.EXPECT_STOPPED,
            timeout=20.0,
            on_success=lambda: self.transition_to(self.STATE_IDLE, "stopped"),
            on_timeout=lambda: self.transition_to(self.STATE_IDLE, "timeout")  # Ensure we reach IDLE even on timeout
        )
    # ===== Lifecycle Methods =====
    
    def close(self):
        """Clean up resources"""
        self.robot.close()
        self.vision.close()


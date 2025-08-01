from PyQt5.QtCore import QObject, pyqtSignal, QTimer
import numpy as np
import time
import yaml

from utils.logger_config import get_logger
from utils.tools import map_image_to_robot, save_image, draw_cross, draw_points, add_border
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

    # State machine states
    STATE_IDLE = "IDLE"
    STATE_MOVING_1 = "MOVING_1"
    STATE_CAPTURING = "CAPTURING"
    STATE_MOVING_2 = "MOVING_2"
    STATE_QUEUEING = "QUEUEING"
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
    
    # batch processing constants
    QUEUE_BATCH_SIZE = 15

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
    
    # ===== Initialization Methods =====
    
    def _init_models(self):
        """Initialize robot and vision models"""
        self.robot = RobotModel(ip=config["robot"]["ip"], port=config["robot"]["port"])
        self.vision = VisionModel(cam_type=config["cam_type"])
        
        # Initialize managers
        self.homo_matrix = config["homo_matrix"]
        self.cross_manager = CrossPositionManager(self.homo_matrix)
        self.centroid_manager = CentroidManager(self.homo_matrix)
        
        # Capture positions
        self.capture_positions = config["capture_positions"]
    
    def _init_ui_state(self):
        """Initialize UI state variables"""
        # Current view state (live/paused/etc.)
        self.current_view_state = "paused orig"
        
        # Current active tab
        self.current_tab = "Engineer"
        
        # List to store cross positions
        self.cross_positions = []
    
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
        self.vision.live_worker.frame_ready.connect(self._on_live_frame_ready)
        self.vision.live_worker.error_occurred.connect(self._on_camera_error)
        
        # Initial status message
        self.status_message.emit("Press R Key to note current cross position")
    
    # ===== Signal Handlers =====
    
    def _on_robot_connected(self):
        """Handle successful robot connection."""
        logger.info("Robot connected successfully")
        self.status_message.emit("Robot connected")
        
    def _on_robot_error(self, error_msg):
        """Handle robot connection error."""
        logger.error(f"Robot error: {error_msg}")
        self.status_message.emit(f"Robot error: {error_msg}")

    def _on_robot_status(self, status_message):
        """Handle robot status messages."""
        self.robot_status_message.emit(status_message)
    
    def _on_frame_processed(self, success):
        """Handle completion of frame processing from the vision model"""
        if success:
            self._update_centroids()
            frame = self._get_frame_for_display(self.current_view_state)
            self._prepare_and_emit_frame(frame)
        else:
            logger.error("Process image failure")
            self.status_message.emit("Process image failure")
            
    def _on_live_frame_ready(self, frame):
        """Handle live frame updates from the live camera thread"""
        if self.current_view_state == "live" and self.current_tab == "Engineer":
            self.vision.frame_camera_live = frame
            self._prepare_and_emit_frame(frame, draw_cells=False)
    
    def _on_camera_error(self, error_message):
        """Handle camera error messages from the worker thread"""
        logger.error(f"Camera error: {error_message}")
        self.status_message.emit(error_message)
    
    # ===== Frame Handling Methods =====
    
    def capture_process_frame(self):
        """Process frame when requested (e.g., via Process button)."""
        if self.current_view_state == "live":
            # In live mode, we're already capturing frames through the live_worker thread
            # Just ensure the live capture is running
            self.vision.live_capture()
        else:
            # For non-live states, stop live capture and get a single frame
            self.vision.stop_live_capture()
            if self.vision.capture_and_process():
                frame = self._get_frame_for_display(self.current_view_state)
                self._prepare_and_emit_frame(frame)
    
    def _prepare_and_emit_frame(self, frame, draw_cells=True):
        """Draw cells and cross on frame then emit"""
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
                size=10,
                row_indices=self.centroid_manager.row_indices
            )
        
        # Draw cross on frame before emitting
        cross_x, cross_y = self.cross_manager.cam_xy
        frame = draw_cross(frame, cross_x, cross_y)
        
        # Add 1px border
        frame = add_border(frame, color=(0, 0, 0), thickness=1)
        
        # Emit the prepared frame
        self.frame_updated.emit(frame)
    
    def _get_frame_for_display(self, view_state):
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
    
    def _update_centroids(self):
        """Helper method to update centroids data from the vision model."""
        _centroids = self.centroid_manager.process_centroids(self.vision.centroids)
        self.cell_max_changed.emit(len(_centroids) - 1 if len(_centroids) > 0 else 0)
    
    # ===== UI Control Methods =====
    
    def set_view_state(self, state):
        """Update the current view state: live, paused orig, paused thres, paused contours."""
        previous_state = self.current_view_state
        self.current_view_state = state
        logger.info(f"View state changed to: {state}")
        
        # Adjust camera based on view state
        if state == "live" and self.current_tab == "Engineer":
            # For live view, use the background thread
            self.vision.live_capture()
        else:
            # For non-live states, stop live capture
            self.vision.stop_live_capture()
            
            # Edge case: If we're switching from live to paused and we don't have a stored frame,
            # capture one first
            if previous_state == "live" and self.vision.frame_camera_stored is None:
                logger.info("Capturing a frame before switching to paused state")
                self.vision.capture_and_process()
            
            # Emit the appropriate frame for this state
            frame = self._get_frame_for_display(state)
            self._prepare_and_emit_frame(frame)

    def set_current_tab(self, tab_name):
        """Set the current active tab."""
        self.current_tab = tab_name
        logger.info(f"Active tab changed to: {tab_name}")
        
        # If changing tabs, update live camera state
        if self.current_view_state == "live":
            if tab_name == "Engineer":
                # Enable live camera in Engineer tab with live view
                self.vision.live_capture()
            else:
                # Disable live camera in other tabs
                self.vision.stop_live_capture()
                # Emit a single frame for the current state
                frame = self._get_frame_for_display(self.current_view_state)
                self._prepare_and_emit_frame(frame)
        else:
            # For non-live states, always ensure live camera is stopped
            self.vision.stop_live_capture()

    def save_current_frame(self):
        """Save the current camera frame to disk."""
        if self.vision.frame_camera_stored is not None and self.vision.frame_camera_stored.size > 0:
            save_image(self.vision.frame_camera_stored, config["save_folder"])
            self.status_message.emit("Frame saved")
        else:
            logger.warning("No frame stored to save.")

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
        
        # Emit status message
        log_msg = f"Cross position updated: {position_info}"
        logger.info(log_msg)
        self.status_message.emit(log_msg)
        
        # Emit an updated frame with the new cross position
        frame = self._get_frame_for_display(self.current_view_state)
        self._prepare_and_emit_frame(frame)
        
    def live_capture(self):
        """Start live camera capture."""
        return self.vision.live_capture()

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
        self.transition_to(self.STATE_MOVING_1)
        return True
    
    def transition_to(self, new_state, reason="success"):
        """
        Transition state machine to a new state
        
        Args:
            new_state: The target state to transition to
            reason: Reason for transition ("success", "timeout", "error", "failure")
        """
        logger.info(f"Operation state transition: {self.current_operation_state} -> {new_state} (reason: {reason})")
        
        # If we're stopping, don't allow transitions to non-idle states
        if hasattr(self, 'stopping') and self.stopping and new_state != self.STATE_IDLE:
            logger.info("Stop requested, ignoring transition to non-idle state")
            return
            
        self.current_operation_state = new_state
        
        # Execute state entry action
        if new_state == self.STATE_MOVING_1:
            self._execute_move_1()
        elif new_state == self.STATE_CAPTURING:
            self._execute_capture()
        elif new_state == self.STATE_MOVING_2:
            self._execute_move_2()
        elif new_state == self.STATE_QUEUEING:
            self._execute_queue()
        elif new_state == self.STATE_INSERTING:
            self._execute_insert()
        elif new_state == self.STATE_TESTING:
            self._execute_test()
        elif new_state == self.STATE_IDLE:
            self.current_operation_mode = self.MODE_IDLE
    
    def _execute_move_1(self):
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
            
    def _execute_capture(self):
        """Execute the capture state"""
        self.vision.stop_live_capture()
        time.sleep(1)
        
        # Try to capture and process image
        for i in range(3):
            if self.vision.capture_and_process():
                if self.centroid_manager.is_centroid_updated_recently():
                    time.sleep(1)
                    self.transition_to(self.STATE_MOVING_2)
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
        self.transition_to(self.STATE_IDLE, "error")

    def _execute_move_2(self):
        """Move to lowered Z position of capture position"""
        # Get section position
        try:
            x, y, z, u = self.get_section(self.operation_section_id)
            self.robot.send(
                cmd=f"move {x} {y} {z-20} {u}",
                expect=self.EXPECT_POSITION_REACHED,
                timeout=5.0,
                on_success=lambda: self.transition_to(
                    self.STATE_IDLE if self.current_operation_mode == self.MODE_CAPTURE else self.STATE_QUEUEING
                ),
                on_timeout=lambda: self.transition_to(self.STATE_IDLE, "timeout")
            )
        except Exception as e:
            logger.error(f"Move failed: {e}")
            self.transition_to(self.STATE_IDLE, "error")

    def _execute_queue(self):
        centroids = self.centroid_manager.robot_centroids
        if not centroids:
            logger.error("No centroids available for queue")
            self.transition_to(self.STATE_IDLE, "error")
            return
        
        # Clear any existing queue first
        self.robot.send(
            cmd="clearqueue",
            expect=self.EXPECT_QUEUE_CLEARED,
            timeout=1.0,
            on_success=self._send_batched_centroids,
            on_timeout=lambda: self.transition_to(self.STATE_IDLE, "timeout")
        )
    
    def _send_batched_centroids(self):
        centroids = self.centroid_manager.robot_centroids
        
        # Send first batch
        self._send_centroid_batch(centroids, 0)
    
    def _send_centroid_batch(self, centroids, start_idx):
        if start_idx >= len(centroids):
            # All batches sent, move to next state

            self.transition_to(
                self.STATE_INSERTING if self.current_operation_mode == self.MODE_INSERT else self.STATE_TESTING
            )
            return
        
        end_idx = min(start_idx + self.QUEUE_BATCH_SIZE, len(centroids))
        batch = centroids[start_idx:end_idx]
        
        # Build the batch command
        queue_cmd = "queue " + " ".join([f"{x:.2f} {y:.2f}" for x, y in batch])
        
        logger.info(f"Queue batch {start_idx}-{end_idx-1}: Start")
        self.robot.send(
            cmd=queue_cmd,
            expect=self.EXPECT_QUEUE_APPENDED,
            timeout=1.0,
            on_success=lambda: self._send_centroid_batch(centroids, end_idx),
            on_timeout=lambda: self.transition_to(self.STATE_IDLE, "timeout")
        )

    def _execute_insert(self):
        """Execute the insertion state"""
        logger.info("Insertion: Start")
        self.robot.send(
            cmd="insert",
            expect=self.EXPECT_INSERT_DONE,
            timeout=60.0,  # Use a reasonable timeout based on queue size
            on_success=lambda: self.transition_to(self.STATE_IDLE),
            on_timeout=lambda: self.transition_to(self.STATE_IDLE, "timeout")
        )

    def _execute_test(self):
        """Execute the testing state"""
        logger.info("Testing: Start")
        self.robot.send(
            cmd="test",
            expect=self.EXPECT_TEST_DONE,
            timeout=60.0,
            on_success=lambda: self.transition_to(self.STATE_IDLE),
            on_timeout=lambda: self.transition_to(self.STATE_IDLE, "timeout")
        )
    
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
        Get the capture position for a given section_id.
        
        Args:
            section_id: Index of the section to retrieve
            
        Returns:
            Tuple of (x, y, z, u) coordinates
        """
        if section_id < 0 or section_id >= len(self.capture_positions):
            raise ValueError(f"Invalid section_id: {section_id}. Must be between 0 and {len(self.capture_positions)-1}")
        
        # Return all 4 elements (x, y, z, u) from the capture position
        return self.capture_positions[section_id]
    
    def change_speed(self, speed):
        """Change the robot speed"""
        logger.info(f"TODO IMPLEMENT THIS: Changing robot speed to {speed}")

        # self.robot.send(cmd=f"speed {speed}")

    def stop_all(self):
        """Stop the current robot operation"""
        logger.info("Stopping robot operation")
        self.robot.send(
            cmd="stop",
            expect=self.EXPECT_STOPPED,
            timeout=2.0,
            on_success=lambda: self.transition_to(self.STATE_IDLE, "stopped"),
            on_timeout=None # No transition on timeout
        )
    # ===== Lifecycle Methods =====
    
    def close(self):
        """Clean up resources"""
        self.robot.close()
        self.vision.close()


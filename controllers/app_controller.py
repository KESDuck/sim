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
    EXPECT_QUEUE_SET = "QUEUE_SET"
    EXPECT_INSERT_DONE = "INSERT_DONE"
    EXPECT_TEST_DONE = "TEST_DONE"

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
        
        # QTimer to update frames
        self.capture_process_frame_timer = QTimer(self)
        self.capture_process_frame_timer.timeout.connect(self.capture_process_frame)
        self.capture_process_frame_timer.start(200)
        
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
            self.vision.live_capture()
        else:
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
                size=10
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
        
        # Adjust frame timer based on view state
        if state == "live" and self.current_tab == "Engineer":
            # For live view, start the timer and use the background thread
            if not self.capture_process_frame_timer.isActive():
                self.capture_process_frame_timer.start(200)
            self.vision.live_capture()
        else:
            # For non-live states, stop the timer and live capture
            if self.capture_process_frame_timer.isActive():
                self.capture_process_frame_timer.stop()
            self.vision.stop_live_capture()
            
            # If we're switching from live to paused and we don't have a stored frame,
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
        
        # If changing tabs, update frame timer state and live camera state
        if self.current_view_state == "live":
            if tab_name == "Engineer":
                if not self.capture_process_frame_timer.isActive():
                    self.capture_process_frame_timer.start(200)
                # Enable live camera in Engineer tab with live view
                self.vision.live_capture()
            else:
                if self.capture_process_frame_timer.isActive():
                    self.capture_process_frame_timer.stop()
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
        if not self.robot.is_connected:
            logger.warning("Robot not connected")
            return False
            
        if self.current_operation_state != self.STATE_IDLE:
            logger.error(f"Cannot start operation: current state is {self.current_operation_state}")
            return False
            
        # Set operation parameters
        self.operation_section_id = section_id
        self.current_operation_mode = mode
        
        # Start the state machine
        self.transition_to(self.STATE_MOVING_1)
        return True
    
    def transition_to(self, new_state):
        """Transition state machine to a new state"""
        logger.info(f"Operation state transition: {self.current_operation_state} -> {new_state}")
        self.current_operation_state = new_state
        
        if self.stopping:
            pass
            # TODO: handle stopping
            

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
            # Operation complete
            self.current_operation_mode = self.MODE_IDLE
            self.status_message.emit(f"{self.current_operation_mode.capitalize()} operation completed")
    
    def _execute_move_1(self):
        """Execute the move to capture position"""
        # Get section position
        try:
            x, y, z = self.get_section(self.operation_section_id)
            self.robot._set_robot_op_state(self.MODE_MOVING)
            self.robot.send(
                cmd=f"move {x} {y} {z}",
                expect=self.EXPECT_POSITION_REACHED,
                timeout=5,
                on_success=lambda: self.transition_to(self.STATE_CAPTURING)
            )
        except Exception as e:
            logger.error(f"Move failed: {e}")
            self.transition_to(self.STATE_IDLE)
            
    def _execute_capture(self):
        """Execute the capture state"""
        self.robot._set_robot_op_state(self.MODE_CAPTURE)
        self.vision.stop_live_capture()
        
        # Try to capture and process image
        for i in range(3):
            if self.vision.capture_and_process():
                if self.centroid_manager.is_centroid_updated_recently():
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
        self.transition_to(self.STATE_IDLE)

    def _execute_move_2(self):
        """Execute the move to lowered Z position of capture position"""
        # Get section position
        try:
            x, y, z = self.get_section(self.operation_section_id)
            self.robot._set_robot_op_state(self.MODE_MOVING)
            self.robot.send(
                cmd=f"move {x} {y} {z-20}",
                expect=self.EXPECT_POSITION_REACHED,
                timeout=5,
                on_success=lambda: self.transition_to(self.STATE_IDLE) \
                    if self.current_operation_mode == self.MODE_CAPTURE \
                    else self.transition_to(self.STATE_QUEUEING)
            )
        except Exception as e:
            logger.error(f"Move failed: {e}")
            self.transition_to(self.STATE_IDLE)

    def _execute_queue(self):
        """Execute the queue state"""
        self.robot._set_robot_op_state(self.MODE_CAPTURE)
        
        # Get the actual centroid data
        centroids = self.centroid_manager.robot_centroids
        if not centroids:
            logger.error("No centroids available for queue")
            self.transition_to(self.STATE_IDLE)
            return
            
        # Build the queue command with actual data
        queue_cmd = "queue " + " ".join([f"{x} {y}" for x, y in centroids])
        
        logger.info("Queue: Start")
        self.robot.send(
            cmd=queue_cmd,
            expect=self.EXPECT_QUEUE_SET,
            timeout=10,
            on_success=lambda: self.transition_to(
                self.STATE_INSERTING if self.current_operation_mode == "insert" else self.STATE_TESTING
            )
        )
            
    def _execute_insert(self):
        """Execute the insertion state"""
        self.robot._set_robot_op_state(self.MODE_INSERT)
        logger.info("Insertion: Start")
        self.robot.send(
            cmd="insert",
            expect=self.EXPECT_INSERT_DONE,
            timeout=60,  # Use a reasonable timeout based on queue size
            on_success=lambda: self.transition_to(self.STATE_IDLE)
        )
        
    def _execute_test(self):
        """Execute the testing state"""
        self.robot._set_robot_op_state(self.MODE_TEST)
        logger.info("Testing: Start")
        self.robot.send(
            cmd="test",
            expect=self.EXPECT_TEST_DONE,
            timeout=60,
            on_success=lambda: self.transition_to(self.STATE_IDLE)
        )
    
    # ===== High-Level Operations =====
    
    def insert_section(self, section_id):
        """Start insertion operation for given section"""
        return self.start_section_operation(section_id, "insert")
    
    def test_section(self, section_id):
        """Start test operation for given section"""
        return self.start_section_operation(section_id, "test")
    
    def stop_insert(self):
        """Stop the current robot operation"""
        # Implementation...
    
    # ===== Lifecycle Methods =====
    
    def close(self):
        """Clean up resources"""
        self.robot.close()
        self.vision.close()


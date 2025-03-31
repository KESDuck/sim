from PyQt5.QtCore import QObject, pyqtSignal, QTimer
import numpy as np
import time
import yaml

from utils.logger_config import get_logger
from utils.tools import map_image_to_robot, save_image, draw_cross, draw_points
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
        self.cam_xy = np.array([1, 1])
        self.robot_xy = None
        self.homo_matrix = homo_matrix

    def shift(self, dx=0, dy=0):
        """Move cross in camera position by delta x,y."""
        x, y = self.cam_xy
        self.set_position(x+dx, y+dy)
        
    def set_position(self, x, y):
        """Set the cross position in camera coordinates."""
        self.cam_xy = np.array([x, y])
        self.robot_xy = map_image_to_robot(self.cam_xy, self.homo_matrix)
        
    def get_position_info(self):
        """Get formatted position information for display."""
        cam_x, cam_y = self.cam_xy
        if self.robot_xy is None:
            return f"Camera: ({cam_x:6.1f}, {cam_y:6.1f}), Robot: (-, -)"
        else:
            robot_x, robot_y = self.robot_xy
            return f"Camera: ({cam_x:6.1f}, {cam_y:6.1f}), Robot: ({robot_x:7.2f}, {robot_y:7.2f})"


class CellManager:
    """
    Manages cell selection and indexing.
    """
    def __init__(self):
        self.cells_xy = None
        self.current_index = -1
        
    def update_cells(self, cells_xy):
        """Update the list of cell coordinates."""
        self.cells_xy = cells_xy
        self.current_index = -1
        return len(self.cells_xy) - 1 if self.cells_xy else 0
        
    def set_index(self, index):
        """Set the current cell index."""
        if self.cells_xy is None:
            self.current_index = -1
            return
        
        # Ensure index is within valid range
        if index < -1:
            index = -1
        elif index >= len(self.cells_xy):
            index = len(self.cells_xy) - 1
            
        self.current_index = index
        
    def get_current_cell(self):
        """Get coordinates of the current cell."""
        if self.current_index < 0 or self.cells_xy is None or self.current_index >= len(self.cells_xy):
            return None
        return self.cells_xy[self.current_index]


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

    def __init__(self):
        super().__init__()
        self.robot = RobotModel()
        self.vision = VisionModel(cam_type=config["cam_type"])

        # Initialize managers
        self.cross_manager = CrossPositionManager(config["homo_matrix"])
        self.cell_manager = CellManager()

        # keep track if it is batch inserting 
        self.pause_insert = False

        # TODO: this determines screw boundaries
        self.capture_position_idx = 0
        self.conveyor_position_idx = 0

        self.capture_positions = config["capture_positions"]
        self.homo_matrix = config["homo_matrix"]

        # QTimer to update frames
        self.frame_timer = QTimer(self)
        self.frame_timer.timeout.connect(self.update_frame)
        # Start timer at ~30fps (33ms interval)
        self.frame_timer.start(100)

        # Current view state (live/paused/etc.)
        self.current_view_state = "paused orig"
        
        # Current active tab ("Engineer" or "User")
        self.current_tab = "Engineer"
        
        # Emit initial status message
        self.status_message.emit("Press R Key to note current cross position")

    def _prepare_and_emit_frame(self, frame, draw_cells=True):
        """Helper method to prepare a frame with overlays and emit it."""
        if frame is None:
            return
            
        # Make a copy to avoid modifying the original
        frame = frame.copy()
        
        # Add overlay with cell points if available and requested
        if draw_cells and self.current_view_state != "live" and self.cell_manager.cells_xy is not None:
            frame = draw_points(
                frame, 
                self.cell_manager.cells_xy, 
                self.cell_manager.current_index, 
                size=10
            )
        
        # Draw cross on frame before emitting
        cross_x, cross_y = self.cross_manager.cam_xy
        frame = draw_cross(frame, cross_x, cross_y)
        
        # Emit the prepared frame
        self.frame_updated.emit(frame)

    def set_view_state(self, state):
        """Update the current view state."""
        self.current_view_state = state
        logger.info(f"View state changed to: {state}")
        
        # Adjust frame timer based on view state
        if state == "live" and self.current_tab == "Engineer":
            if not self.frame_timer.isActive():
                self.frame_timer.start(100)
        else:
            # For non-live states, stop continuous updates but emit a single frame
            if self.frame_timer.isActive():
                self.frame_timer.stop()
            
            # Emit the appropriate frame for this state
            frame = self.get_frame_for_display(state)
            self._prepare_and_emit_frame(frame)

    def _update_centroids(self):
        """Helper method to update centroids data from the vision model."""
        max_value = self.cell_manager.update_cells(self.vision.centroids)
        self.cell_index_changed.emit(-1)
        self.cell_max_changed.emit(max_value)
        logger.info(f"Updated centroids, found {max_value + 1}")

    def update_frame(self):
        """Process frame when requested (e.g., via Process button)."""
        # Get the current state
        logger.info(f"Updating frame in state: {self.current_view_state}")
        if self.current_view_state == "live":
            # For live mode, just capture a new frame
            if self.vision.live_capture():
                frame = self.vision.frame_camera_live
                self._prepare_and_emit_frame(frame, draw_cells=False)
        else:
            # For non-live modes, process the frame
            if self.vision.capture_and_process():
                # Update centroids data
                self._update_centroids()
                
                # Get the processed frame based on current view state
                frame = self.get_frame_for_display(self.current_view_state)
                self._prepare_and_emit_frame(frame)
            else:
                logger.error("Process image failure")
                self.status_message.emit("Process image failure")

    def insert_batch(self, capture_idx) -> bool:
        """
        Insert batch for the given insertion region. 2 steps:
        1. position_and_capture
        2. insert_all_in_view
        """
        if not self.position_and_capture(capture_idx):
            logger.error(f"Capture failed at index {capture_idx}")
            return False
        
        if not self.insert_all_in_view():
            logger.error("Insertion failed.")
            return False
        
        logger.info(f"Insertion region {capture_idx} completed successfully.")
        return True

    def position_and_capture(self, idx=None) -> bool:
        """
        Move robot to capture position, then capture and process a frame
        """
        if idx is None:
            idx = self.capture_position_idx
        x, y, z, u = self.capture_positions[idx]
        self.robot.jump(x, y, z, 0)
        for attempts in range(3):
            if self.vision.capture_and_process():
                # Update centroids data
                self._update_centroids()
                break
            logger.info("Capture failure, retrying...")
            time.sleep(1)
        else:
            logger.error("All capture attempts failed")
            self.status_message.emit("All capture attempts failed")
            return False
        self.robot.jump(x, y, -18., 0)
        
        # Update the view with the new frame
        frame = self.get_frame_for_display(self.current_view_state)
        self._prepare_and_emit_frame(frame)
        return True

    def insert_all_in_view(self) -> bool:
        """
        Insert begin from cell_index, can be paused and resumed
        TODO: Stop if error such as socket not connected, if "ack" or "taskdone" not received after timeout
        """
        while self.cell_manager.current_index < len(self.cell_manager.cells_xy) - 1:
            if self.pause_insert:
                break
            self.set_cell_index(self.cell_manager.current_index + 1)
            if not self.cell_action("insert"):
                # TODO: pause the UI here not just insertion toggle_pause_insert
                logger.error("Something is wrong, please check.")
                return False
        return True

    def cell_action(self, action="insert") -> bool:
        current_cell = self.cell_manager.get_current_cell()
        if current_cell is None:
            msg = "Bad cell index"
            logger.warning(msg)
            self.status_message.emit(msg)
            return False
        
        cX, cY = current_cell
        rX, rY = map_image_to_robot((cX, cY), self.homo_matrix)

        if action == "insert":
            success = self.robot.insert(rX, rY, config['robot']['z_insert'], 0)
            action_msg = "Insert"
        elif action == "jump":
            success = self.robot.jump(rX, rY, config['robot']['z_insert'], 0)
            action_msg = "Jump"
        else:
            raise ValueError("Bad action")

        if not success:
            self.status_message.emit(f"{action_msg} failed at cell {self.cell_manager.current_index}")
            return False
        
        self.status_message.emit(f"{action_msg} successful at cell {self.cell_manager.current_index}")
        return success

    def save_current_frame(self):
        if self.vision.frame_camera_stored is not None and self.vision.frame_camera_stored.size > 0:
            save_image(self.vision.frame_camera_stored, config["save_folder"])
            self.status_message.emit("Frame saved")
        else:
            logger.warning("No frame stored to save.")

    def echo_test(self):
        self.robot.echo()
        self.status_message.emit("Echo command sent")

    def shift_cross(self, dx=0, dy=0):
        """Move cross in camera position."""
        self.cross_manager.shift(dx, dy)
        
        # Emit an updated frame with the new cross position
        frame = self.get_frame_for_display(self.current_view_state)
        self._prepare_and_emit_frame(frame)
        
        # Emit status message
        x, y = self.cross_manager.cam_xy
        log_msg = f"Cross position updated to ({x}, {y})"
        logger.info(log_msg)
        self.status_message.emit(log_msg)

    def set_cross_position(self, x, y):
        """Set the cross position in camera coordinates."""
        self.cross_manager.set_position(x, y)
        
        # Emit an updated frame with the new cross position
        frame = self.get_frame_for_display(self.current_view_state)
        self._prepare_and_emit_frame(frame)
        
        # Emit status message
        log_msg = f"Cross position updated to ({x}, {y})"
        logger.info(log_msg)
        self.status_message.emit(log_msg)

    def set_cell_index(self, index):
        """Update cell index and notify view."""
        self.cell_manager.set_index(index)
        self.cell_index_changed.emit(self.cell_manager.current_index)
        
        # Update the display with the new cell selection
        if self.current_view_state != "live" and self.cell_manager.cells_xy is not None:
            frame = self.get_frame_for_display(self.current_view_state)
            self._prepare_and_emit_frame(frame)

    def toggle_pause_insert(self):
        self.pause_insert = not self.pause_insert
        if self.pause_insert:
            msg = f"Insertion paused at {self.cell_manager.current_index}"
        else:
            msg = f"Insertion resumed at {self.cell_manager.current_index}"
        
        logger.info(msg)
        self.status_message.emit(msg)

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
        
        # If changing tabs, update frame timer state
        if self.current_view_state == "live":
            if tab_name == "Engineer" and not self.frame_timer.isActive():
                self.frame_timer.start(100)
            elif tab_name != "Engineer" and self.frame_timer.isActive():
                self.frame_timer.stop()
                # Emit a single frame for the current state
                frame = self.get_frame_for_display(self.current_view_state)
                self._prepare_and_emit_frame(frame) 
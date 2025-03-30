from PyQt5.QtCore import QObject, pyqtSignal, QTimer
import numpy as np
import time
import yaml

from utils.logger_config import get_logger
from utils.tools import map_image_to_robot, save_image, draw_cross
from models.robot_model import RobotModel
from models.vision_model import VisionModel

logger = get_logger("Controller")
with open('config.yml', 'r') as file:
    config = yaml.safe_load(file)


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

        self.cross_cam_xy = np.array([1, 1])
        self.cross_robo_xy = None

        # Cells xy are retrieved from vision model
        self.cells_img_xy = None
        self.cell_index = -1  # Single source of truth for cell index

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
        self.frame_timer.start(33)

        # Current view state (live/paused/etc.)
        self.current_view_state = "paused orig"
        
        # Emit initial status message
        self.status_message.emit("Press R Key to note current cross position")

    def set_view_state(self, state):
        """Update the current view state."""
        self.current_view_state = state
        logger.info(f"View state changed to: {state}")
        
        # Adjust frame timer based on view state
        if state == "live":
            if not self.frame_timer.isActive():
                self.frame_timer.start(33)
        else:
            # For non-live states, stop continuous updates but emit a single frame
            if self.frame_timer.isActive():
                self.frame_timer.stop()
            
            # Emit the appropriate frame for this state
            frame = self.get_frame_for_display(state)
            if frame is not None:
                # Make a copy to avoid modifying the original
                frame = frame.copy()
                
                # For non-live frames, add overlay with cell points if available
                if state != "live" and self.cells_img_xy is not None:
                    from utils.tools import draw_points
                    frame = draw_points(
                        frame, 
                        self.cells_img_xy, 
                        self.cell_index, 
                        size=10
                    )
                
                # Draw cross on frame before emitting
                cross_x, cross_y = self.cross_cam_xy
                frame = draw_cross(frame, cross_x, cross_y)
                
                self.frame_updated.emit(frame)

    def update_frame(self):
        """Grab a live frame from the vision model and emit the frame_updated signal."""
        if self.current_view_state == "live":
            # For live mode, capture a new frame
            if self.vision.live_capture():
                frame = self.vision.frame_camera_live
                if frame is not None:
                    # Draw cross on frame before emitting
                    frame = frame.copy()  # Make a copy to avoid modifying the original
                    cross_x, cross_y = self.cross_cam_xy
                    frame = draw_cross(frame, cross_x, cross_y)
                    self.frame_updated.emit(frame)
            else:
                logger.warning("Live capture failed. Skipped frame update.")

    def process_frame(self):
        """Process frame when requested (e.g., via Process button)."""
        # Get the current state
        if self.current_view_state == "live":
            # For live mode, just capture a new frame
            if self.vision.live_capture():
                frame = self.vision.frame_camera_live
                if frame is not None:
                    # Draw cross on frame before emitting
                    frame = frame.copy()  # Make a copy to avoid modifying the original
                    cross_x, cross_y = self.cross_cam_xy
                    frame = draw_cross(frame, cross_x, cross_y)
                    self.frame_updated.emit(frame)
        else:
            # For non-live modes, process the frame
            if self.vision.capture_and_process():
                # Update centroids data
                self.cells_img_xy = self.vision.centroids
                self.set_cell_index(-1)
                max_value = len(self.cells_img_xy) - 1 if self.cells_img_xy else 0
                self.cell_max_changed.emit(max_value)
                
                # Get the processed frame based on current view state
                frame = self.get_frame_for_display(self.current_view_state)
                if frame is not None:
                    # Make a copy to avoid modifying the original
                    frame = frame.copy()
                    
                    # Add overlay with cell points if available
                    if self.cells_img_xy is not None:
                        from utils.tools import draw_points
                        frame = draw_points(
                            frame, 
                            self.cells_img_xy, 
                            self.cell_index, 
                            size=10
                        )
                    
                    # Draw cross on frame before emitting
                    from utils.tools import draw_cross
                    cross_x, cross_y = self.cross_cam_xy
                    frame = draw_cross(frame, cross_x, cross_y)
                    
                    self.frame_updated.emit(frame)
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
                self.cells_img_xy = self.vision.centroids
                self.set_cell_index(-1)
                max_value = len(self.cells_img_xy) - 1 if self.cells_img_xy else 0
                self.cell_max_changed.emit(max_value)
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
        if frame is not None:
            # Make a copy and draw features
            frame = frame.copy()
            
            # Add cell points
            if self.cells_img_xy is not None:
                from utils.tools import draw_points
                frame = draw_points(
                    frame, 
                    self.cells_img_xy, 
                    self.cell_index, 
                    size=10
                )
            
            # Draw cross
            cross_x, cross_y = self.cross_cam_xy
            frame = draw_cross(frame, cross_x, cross_y)
            
            self.frame_updated.emit(frame)
            
        return True

    def insert_all_in_view(self) -> bool:
        """
        Insert begin from cell_index, can be paused and resumed
        TODO: Stop if error such as socket not connected, if "ack" or "taskdone" not received after timeout
        """
        while self.cell_index < len(self.cells_img_xy) - 1:
            if self.pause_insert:
                break
            self.set_cell_index(self.cell_index + 1)
            if not self.cell_action("insert"):
                # TODO: pause the UI here not just insertion toggle_pause_insert
                logger.error("Something is wrong, please check.")
                return False
        return True

    def cell_action(self, action="insert") -> bool:
        if self.cell_index < 0 or self.cell_index >= len(self.cells_img_xy or []):
            msg = "Bad cell index"
            logger.warning(msg)
            self.status_message.emit(msg)
            return False
        
        cX, cY = self.cells_img_xy[self.cell_index]
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
            self.status_message.emit(f"{action_msg} failed at cell {self.cell_index}")
            return False
        
        self.status_message.emit(f"{action_msg} successful at cell {self.cell_index}")
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
        """
        Move cross in camera position
        TODO[b]: allow for half step movement
        """
        x, y = self.cross_cam_xy
        self.set_cross_position(x+dx, y+dy)

    def set_cross_position(self, x, y):
        """
        Set the cross position in camera coordinates
        TODO: check for boundaries
        """
        self.cross_cam_xy = np.array([x, y])
        self.cross_robo_xy = map_image_to_robot(self.cross_cam_xy, self.homo_matrix)
        
        # Emit an updated frame with the new cross position
        frame = self.get_frame_for_display(self.current_view_state)
        if frame is not None:
            # Make a copy and draw cross
            from utils.tools import draw_cross
            frame = frame.copy()
            
            # Add cell points if in non-live mode
            if self.current_view_state != "live" and self.cells_img_xy is not None:
                from utils.tools import draw_points
                frame = draw_points(
                    frame, 
                    self.cells_img_xy, 
                    self.cell_index, 
                    size=10
                )
            
            # Draw the cross at new position
            frame = draw_cross(frame, x, y)
            
            self.frame_updated.emit(frame)
        
        # Emit status message
        log_msg = f"Cross position updated to ({x}, {y})"
        logger.info(log_msg)
        self.status_message.emit(log_msg)

    def print_cross_position(self):
        """
        Print current cross position for calibration purposes
        """
        cam_x, cam_y = self.cross_cam_xy
        if self.cross_robo_xy is None:
            msg = f"Camera: ({cam_x:6.1f}, {cam_y:6.1f}), Robot: (-, -)"
        else:
            robot_x, robot_y = self.cross_robo_xy
            msg = f"Camera: ({cam_x:6.1f}, {cam_y:6.1f}), Robot: ({robot_x:7.2f}, {robot_y:7.2f})"
        
        logger.info(msg)
        self.status_message.emit(msg)

    def set_cell_index(self, index):
        """Update cell index and notify view."""
        self.cell_index = index
        self.cell_index_changed.emit(index)
        
        # Update the display with the new cell selection
        if self.current_view_state != "live" and self.cells_img_xy is not None:
            frame = self.get_frame_for_display(self.current_view_state)
            if frame is not None:
                # Make a copy to avoid modifying the original
                frame = frame.copy()
                
                # Draw points for cells
                from utils.tools import draw_points
                frame = draw_points(
                    frame, 
                    self.cells_img_xy, 
                    self.cell_index, 
                    size=10
                )
                
                # Draw cross
                from utils.tools import draw_cross
                cross_x, cross_y = self.cross_cam_xy
                frame = draw_cross(frame, cross_x, cross_y)
                
                self.frame_updated.emit(frame)

    def toggle_pause_insert(self):
        self.pause_insert = not self.pause_insert
        if self.pause_insert:
            msg = f"Insertion paused at {self.cell_index}"
        else:
            msg = f"Insertion resumed at {self.cell_index}"
        
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
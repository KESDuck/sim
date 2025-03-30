from PyQt5.QtCore import QObject, pyqtSignal
import numpy as np
import time
import yaml

from utils.logger_config import get_logger
from utils.tools import map_image_to_robot, save_image
from models.robot_model import RobotModel
from models.vision_model import VisionModel

logger = get_logger("Controller")
with open('config.yml', 'r') as file:
    config = yaml.safe_load(file)


class AppController(QObject):
    """
    Controller that coordinates between models and views.
    Manages centroids selection, robot positioning, and processing flow.
    """
    cell_index_changed = pyqtSignal(int)
    cell_max_changed = pyqtSignal(int)

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

        # Capture and conveyor positions
        self.capture_position_idx = 0
        self.conveyor_position_idx = 0

        self.capture_positions = config["capture_positions"]
        self.homo_matrix = config["homo_matrix"]

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
        Move robot to capture position. 
        Capture and process with 3 attempts
        Then lower the z to allow for jump limZ
        """
        if idx is None:
            idx = self.capture_position_idx
            
        x, y, z, u = self.capture_positions[idx]
        self.robot.jump(x, y, z, 0)
        
        for attempts in range(3):
            if self.capture_and_process():
                break
            logger.info("Capture failure, retrying...")
            time.sleep(1)
        else:
            logger.error("All capture attempts failed")
            return False
        
        self.robot.jump(x, y, -18., 0)
        return True

    def capture_and_process(self) -> bool:
        """
        Trigger vision model to capture and process
        Update centroids data
        """
        if self.vision.capture_and_process():
            self.cells_img_xy = self.vision.centroids
            self.set_cell_index(-1)
            max_value = len(self.cells_img_xy) - 1 if self.cells_img_xy else 0
            self.cell_max_changed.emit(max_value) 
            return True
        else:
            return False
    
    def live_capture(self) -> bool:
        return self.vision.live_capture()

    def insert_all_in_view(self) -> bool:
        """
        Insert begin from cell_index, can be paused and resumed
        """
        while self.cell_index < len(self.cells_img_xy) - 1:
            if self.pause_insert:
                break
            self.set_cell_index(self.cell_index + 1)
            if not self.cell_action("insert"):
                logger.error("Something is wrong, please check.")
                return False
        return True

    def cell_action(self, action="insert") -> bool:
        if self.cell_index < 0 or self.cell_index >= len(self.cells_img_xy):
            logger.warning("Bad cell index")
            return False
        
        cX, cY = self.cells_img_xy[self.cell_index]
        rX, rY = map_image_to_robot((cX, cY), self.homo_matrix)

        if action == "insert":
            success = self.robot.insert(rX, rY, config['robot']['z_insert'], 0)
        elif action == "jump":
            success = self.robot.jump(rX, rY, config['robot']['z_insert'], 0)
        else:
            raise ValueError("Bad action")

        if not success:
            return False
        
        return success

    def save_current_frame(self):
        if self.vision.frame_camera_stored:
            save_image(self.vision.frame_camera_stored, config["save_folder"])

    def echo_test(self):
        self.robot.echo()

    def shift_cross(self, dx=0, dy=0):
        """Move cross in camera position"""
        x, y = self.cross_cam_xy
        self.set_cross_position(x+dx, y+dy)

    def set_cross_position(self, x, y):
        """Set the cross position in camera coordinates"""
        self.cross_cam_xy = np.array([x, y])
        self.cross_robo_xy = map_image_to_robot(self.cross_cam_xy, self.homo_matrix)

    def print_cross_position(self):
        """For fine tuning homography use."""
        cam_x, cam_y = self.cross_cam_xy
        
        if self.cross_robo_xy is None:
            logger.info(f"Camera: ({cam_x:6.1f}, {cam_y:6.1f}), Robot: (-, -)")
        else:
            robot_x, robot_y = self.cross_robo_xy
            logger.info(f"Camera: ({cam_x:6.1f}, {cam_y:6.1f}), Robot: ({robot_x:7.2f}, {robot_y:7.2f})")

    def set_cell_index(self, index):
        """Update cell index and notify view."""
        self.cell_index = index
        self.cell_index_changed.emit(index)

    def toggle_pause_insert(self):
        self.pause_insert = not self.pause_insert
        if self.pause_insert:
            logger.info(f"Insertion paused at {self.cell_index}")
        else:
            logger.info(f"Insertion resumed at {self.cell_index}")

    def get_frame_for_display(self, view_state):
        """Get appropriate frame based on view state"""
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

    def close(self):
        """Clean up resources"""
        self.robot.close()
        self.vision.close() 
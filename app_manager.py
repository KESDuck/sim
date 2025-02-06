from PyQt5.QtCore import QObject, pyqtSignal
import numpy as np

import yaml
from logger_config import get_logger
from robot_manager import RobotManager
from vision_manager import VisionManager
from tools import map_image_to_robot, save_image

logger = get_logger("Manager")
with open('config.yml', 'r') as file:
    config = yaml.safe_load(file)


class AppManager(QObject):
    """
    Handles all the coordination between vision, robot, TODO conveyor, and UI.
    Manages detected cells (centroids).
    Manages cross positions.
    Manages processing section - capture position and conveyor position.
    Robot position, send cell positions to robot.
    """
    cell_index_changed = pyqtSignal(int)

    def __init__(self):
        super().__init__()  # Required for QObject signals to work
        self.robot = RobotManager()
        self.vision = VisionManager(cam_type=config["cam_type"])

        self.cross_cam_xy = np.array([1, 1])
        self.cross_robo_xy = None

        # Cells xy are retrived from vision manager
        # cell_index controlled by app_ui
        self.cells_img_xy = None
        self.cell_index = -1 # Single source of truth for cell index

        # keep track if it is batch inserting 
        self.pause_insert = False


        # TODO: this determines screw boundaries
        self.capture_position_idx = 0
        self.conveyor_position_idx = 0

        self.capture_positions = config["capture_positions"]
        self.homo_matrix = config["homo_matrix"]

    def insert_batch(self, capture_idx):
        """
        Insert bath for position given capture_idx
        Automated from capturing to inserting all
        TODO: work on it later
        """
        self.move_to_capture_position(capture_idx)
        self.capture_and_process(process=True)
        self.insert_all_in_view()

    def move_to_capture_position(self, idx):
        """
        Move robot for vision position. Move conveyor for conveyor position
        """
        x, y, z, u = self.capture_positions[idx]
        self.robot.move(x, y, z, u)

    def capture_and_process(self, process=False):
        """
        TODO: check z. sometimes it is not in position, do not capture if not in correct z height
        """
        self.vision.capture_and_process(process)
        if process:
            self.cells_img_xy = self.vision.centroids
            self.set_cell_index(-1)

    def insert_all_in_view(self):
        """
        Insert begin from cell_index, can be paused and resumed
        Button to pause
        TODO Stop if error shuch as socket not connected, if "ack" or "taskdone" not received after timeout
        """

        while self.cell_index < len(self.cells_img_xy) - 1:
            if self.pause_insert:
                break

            self.set_cell_index(self.cell_index + 1)

            # If return false that means there is something wrong
            if not self.cell_action(action="jump"):
                # TODO: pause the UI here
                logger.warning("Something is wrong, please check.")
                break

    def cell_action(self, action="insert"):
        if self.cell_index < 0 or self.cell_index >= len(self.cells_img_xy):
            logger.warning("Bad cell index.")
            return  # Ignore invalid indices
        
        cX, cY = self.cells_img_xy[self.cell_index]
        rX, rY = map_image_to_robot((cX, cY), self.homo_matrix)

        if action == "insert":
            return self.robot.insert(rX, rY, config['robot']['z_insert'])
        elif action == "jump":
            return self.robot.jump(rX, rY, config['robot']['z_insert'])
        else:
            logger.error("Bad action")

    def on_save_frame(self):
        if self.vision.frame_camera_stored:
            save_image(self.vision.frame_camera_stored, config["save_folder"])

    def echo_test(self):
        self.robot.echo()

    def shift_cross(self, dx=0, dy=0):
        """In camera position
        # TODO: check for boundaries of the cross
        """
        x, y = self.cross_cam_xy
        self.set_cross_position(x+dx, y+dy)

    def set_cross_position(self, x, y):
        self.cross_cam_xy = np.array([x, y])
        self.cross_robo_xy = map_image_to_robot(self.cross_cam_xy, self.homo_matrix)

    def print_cross_position(self):
        """For fine tuning homography use.
        Save at least 9 robot position and current cross position pair to recalibrate

        Print format: Camera: (123, 456), Robot: (123.45, 678.90)
        """
        cam_x, cam_y = self.cross_cam_xy
        if self.cross_robo_xy is None:
            logger.info(f"Camera: ({cam_x}, {cam_y}), Robot: (-, -)")
        else:
            robot_x, robot_y = self.cross_robo_xy
            logger.info(f"Camera: ({cam_x}, {cam_y}), Robot: ({robot_x:.2f}, {robot_y:.2f})")

    def set_cell_index(self, index):
        """Update cell index and notify UI."""
        self.cell_index = index
        self.cell_index_changed.emit(index)  # Notify UI

    def toggle_pause_insert(self):
        self.pause_insert = not self.pause_insert
        if self.pause_insert:
            logger.info(f"Insertion paused at {self.cell_index}")
        else:
            logger.info(f"Insertion resumed at {self.cell_index}")

    def close(self):
        # close socket connection
        self.robot.close()

        # close camera
        self.vision.close()

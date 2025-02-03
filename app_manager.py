from PyQt5.QtCore import QTimer
import numpy as np

import yaml
from logger_config import get_logger
from robot_manager import RobotManager
from vision_manager import VisionManager
from tools import map_image_to_robot, save_image

logger = get_logger("Manager")
with open('config.yml', 'r') as file:
    config = yaml.safe_load(file)


class AppManager():
    """
    Handles all the coordination between vision, robot, TODO conveyor, and UI.
    Manages detected cells (centroids).
    Manages cross positions.
    Manages processing section - capture position and conveyor position.
    Robot position, send cell positions to robot.
    """
    def __init__(self):
        self.robot = RobotManager()
        self.vision = VisionManager(cam_type=config["cam_type"])

        self.cam_xy_cross = np.array([1, 1])
        self.robo_xy_cross = None

        self.cells = None
        self.cell_index = -1

        # TODO: this determines screw boundaries
        self.capture_position_idx = 0
        self.conveyor_position_idx = 0

        self.capture_positions = config["capture_positions"]
        self.homo_matrix = config["homo_matrix"]
    
    def insert_all_in_view(self, capture_idx):
        """
        TODO WIP
        """
        self.move_to_capture_position(capture_idx)
        self.capture_and_process(process=True)
        for centroid in self.vision.centroids:
            cX, cY = centroid
            rX, rY = map_image_to_robot((cX, cY), self.homo_matrix)
            self.robot.insert_single(rX, rY)


    def move_to_capture_position(self, idx):
        """
        Move robot for vision position. Move conveyor for conveyor position
        """
        x, y, z, u = self.capture_positions[idx]
        self.robot.move(x, y, z, u)

    def capture_and_process(self, process=False):
        """
        TODO: sometimes it is not in position, do not capture if not in correct z height
        """
        self.vision.capture_and_process(process)

    def on_save_frame(self):
        if self.vision.frame_camera_stored:
            save_image(self.vision.frame_camera_stored, config["save_folder"])

    def jump_xy(self):
        pass
    

    def echo_test(self):
        self.robot.echo()

    def on_save_frame(self):
        pass

    def shift_cross(self, dx=0, dy=0):
        """In camera position
        # TODO: check for boundaries of the cross
        """
        x, y = self.cam_xy_cross
        self.set_cross_position(x+dx, y+dy)

    def set_cross_position(self, x, y):
        self.cam_xy_cross = np.array([x, y])
        self.robo_xy_cross = map_image_to_robot(self.cam_xy_cross, self.homo_matrix)

    def print_cross_position(self):
        """For fine tuning homography use.
        Save at least 9 robot position and current cross position pair to recalibrate

        Print format: Camera: (123, 456), Robot: (123.45, 678.90)
        """
        cam_x, cam_y = self.cam_xy_cross
        if self.robo_xy_cross is None:
            logger.info(f"Camera: ({cam_x}, {cam_y}), Robot: (-, -)")
        else:
            robot_x, robot_y = self.robo_xy_cross
            logger.info(f"Camera: ({cam_x}, {cam_y}), Robot: ({robot_x:.2f}, {robot_y:.2f})")

    def close(self):
        # close socket connection
        self.robot.close()

        # close camera
        self.vision.close()

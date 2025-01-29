from PyQt5.QtCore import QTimer
import numpy as np

from logger_config import get_logger
from robot_manager import RobotManager
from vision_manager import VisionManager
from tools import map_image_to_robot, draw_cross, draw_points, save_image
from config import CAMERA_MATRIX, HOMO_MATRIX

logger = get_logger("Manager")


class AppManager():
    """
    Handles all the coordination between vision, robot, and UI
    Robot position, send deteced cells position to robot
    Draw current points and detected cells on frame
    """
    def __init__(self):
        self.robot = RobotManager()
        self.vision = VisionManager()

        # cross xy starting at camera's focal point
        self.cam_xy_cross = np.array([int(CAMERA_MATRIX[0][2]), int(CAMERA_MATRIX[1][2])])
        self.robo_xy_cross = None

        # state to save frame, TODO remove this state
        self.save_next_frame = False

    def capture_and_process(self):
        self.vision.capture_and_process()

    # def cycle_vision(self):

    def on_save_frame(self):
        pass

    def jump_xy(self):
        pass
    
    def insert_single(self):
        pass

    def insert_all_in_view(self):
        pass


    def echo_test(self):
        self.robot.echo()

    def print_pos_info(self):
        """For fine tuning homography use.
        Will print out:
            - Last command's robot position
            - Current cross position
        Save at least 9 robot position and current cross position pair to recalibrate
        (img_x(px), img_y, robo_x(mm), robo_y)
        """
        if self.robot.last_position:
            img_x, img_y = self.cam_xy_cross
            robo_x, robo_y, _, _ = self.robot.last_position
            logger.info(f"        ({img_x}, {img_y}, {robo_x}, {robo_y})")
        else:
            img_x, img_y = self.cam_xy_cross
            logger.info(f"        ({img_x}, {img_y}, robo_x, robo_y)")

    def on_save_frame(self):
        self.save_next_frame = True

    def set_cross_position(self, x, y):
        self.cam_xy_cross = np.array([x, y])
        self.robo_xy_cross = map_image_to_robot(self.cam_xy_cross, HOMO_MATRIX)
        # logger.info(f"Camera: {self.cam_xy_cross}, Robot: {self.robo_xy_cross}")

    def close(self):
        # close socket connection
        self.robot.close()

        # close camera
        self.vision.close()

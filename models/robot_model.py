from PyQt5.QtCore import QObject, pyqtSignal
import numpy as np
import yaml
import time

from utils.logger_config import get_logger
from models.robot_socket import RobotSocket

logger = get_logger("Robot")
with open('config.yml', 'r') as file:
    config = yaml.safe_load(file)

class RobotModel(QObject):
    """
    Model that handles robot control.
    Manages communication with the robot through a socket connection.
    """
    def __init__(self):
        super().__init__()
        self.socket = RobotSocket(
            ip=config["robot"]["ip"],
            port=config["robot"]["port"],
            timeout=config["robot"]["timeout"]
        )
        self.connected = self.socket.connect()
        if not self.connected:
            logger.error("Socket failed to connect!")
        else:
            logger.info("Socket connected successfully!")

    def jump(self, x, y, z, u) -> bool:
        """
        Move robot to target position (x, y, z, u)
        """
        if not self.connected:
            logger.error("Socket not connected, cannot jump.")
            return False

        command = f"JUMP,{x:.2f},{y:.2f},{z:.2f},{u:.2f}"
        if self.socket.send_and_wait(command):
            logger.info(f"Jump to: {x:.2f}, {y:.2f}, {z:.2f}, {u:.2f}")
            return True
        else:
            logger.error(f"Jump failed to: {x:.2f}, {y:.2f}, {z:.2f}, {u:.2f}")
            return False

    def insert(self, x, y, z, u) -> bool:
        """
        Perform insertion at target position (x, y, z, u)
        """
        if not self.connected:
            logger.error("Socket not connected, cannot insert.")
            return False

        command = f"INSERT,{x:.2f},{y:.2f},{z:.2f},{u:.2f}"
        if self.socket.send_and_wait(command):
            logger.info(f"Insert at: {x:.2f}, {y:.2f}, {z:.2f}, {u:.2f}")
            return True
        else:
            logger.error(f"Insert failed at: {x:.2f}, {y:.2f}, {z:.2f}, {u:.2f}")
            return False

    def echo(self) -> bool:
        """
        Test connection with echo command
        """
        if not self.connected:
            logger.error("Socket not connected, cannot echo.")
            return False

        command = "ECHO"
        if self.socket.send_and_wait(command):
            logger.info("Echo successful")
            return True
        else:
            logger.error("Echo failed")
            return False

    def close(self):
        """
        Close socket connection
        """
        if self.connected:
            self.socket.close()
            self.connected = False
            logger.info("Socket connection closed") 
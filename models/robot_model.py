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
        # Default connection values if not specified in config
        robot_ip = config.get("robot", {}).get("ip", "127.0.0.1")
        robot_port = config.get("robot", {}).get("port", 8080)
        robot_timeout = config.get("robot", {}).get("timeout", 5.0)
        
        logger.info(f"Connecting to robot at {robot_ip}:{robot_port}")
        
        self.socket = RobotSocket(
            ip=robot_ip,
            port=robot_port,
            timeout=robot_timeout
        )
        
        # Only try to connect if we have valid connection info
        if robot_ip != "127.0.0.1":  # Not using localhost default
            self.connected = self.socket.connect()
            if not self.connected:
                logger.error("Socket failed to connect!")
            else:
                logger.info("Socket connected successfully!")
        else:
            logger.warning("Using offline mode - no robot connection")
            self.connected = False

    def jump(self, x, y, z, u) -> bool:
        """
        Move robot to target position (x, y, z, u)
        """
        if not self.connected:
            logger.warning(f"Offline mode - jump to: {x:.2f}, {y:.2f}, {z:.2f}, {u:.2f}")
            return True  # Pretend success in offline mode

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
            logger.warning(f"Offline mode - insert at: {x:.2f}, {y:.2f}, {z:.2f}, {u:.2f}")
            return True  # Pretend success in offline mode

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
            logger.warning("Offline mode - echo test")
            return True  # Pretend success in offline mode

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
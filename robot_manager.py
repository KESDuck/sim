from logger_config import get_logger
from robot_socket import RobotSocket


logger = get_logger("Robot")


class RobotManager:
    """
    Controls robot-specific functionality.
    """
    def __init__(self, ip="192.168.0.1", port=8501):
        self.client = RobotSocket(ip, port)
        self.client.connect()
        self.last_position = None # Use for tuning homography matrix tuning, old name: last_point

    def echo(self):
        """
        Sending: echo 0 1 2 3
        Received: ack
        Received: echo 0 1 2 3
        Received: taskdone
        """
        self.client.send_command(f"echo 0 1 2 3")

    def jump_xy(self, x, y):
        command = f"jump {x:.2f} {y:.2f} -75.0 0.0"
        logger.info(f"Executing: {command}")
        self.client.send_command(command)
        self.last_position = [x, y, -75, 0]

    def insert_single(self, x, y):
        command = f"insert {x:.2f} {y:.2f} -140.0 0.0"
        logger.info(f"Executing: {command}")
        self.client.send_command(command)

    def insert_all(self, cells):
        """Insert all in the view"""
        pass

    def close(self):
        self.client.close()




#     def jump_xy(self):
#         if self.robo_cross_pos is not None:
#             x, y = self.robo_cross_pos
#             self.robot_client.send_command(f"jump {x:.2f} {y:.2f} -75 180")
#             self.robot_last_position = [x, y, -75, 180]

#     def insert_single(self):
#         """Insert single screw (cross position)"""
#         if self.robo_cross_pos is not None:
#             x, y = self.robo_cross_pos
#             self.robot_client.send_command(f"insert {x:.2f} {y:.2f} -140 180")
#             self.robot_last_position = None
    

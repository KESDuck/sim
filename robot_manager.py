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
        return self.client.send_command(f"echo")

    def where(self):
        """
        TODO Needed to check if camera is at right position. Should return robot position as list of int
        Example output:
        Sending: where
        Received: ack
        Received: X: 50.0888, Y: 470.001, Z: -0.0329844, U: 0.0062027
        Received: taskdone
        """
        return self.client.send_command(f"where")

    def move(self, x, y, z, u):
        command = f"move {x:.2f} {y:.2f} {z:.2f} {u:.2f}"
        return self.client.send_command(command)

    def jump(self, x, y, z, u, limZ=0):
        command = f"jump {x:.2f} {y:.2f} {z:.2f} {u:.2f} {limZ:.2f}"
        return self.client.send_command(command)

    def insert(self, x, y, z, u):
        command = f"insert {x:.2f} {y:.2f} 0 0"
        return self.client.send_command(command)

    def close(self):
        self.client.close()


if __name__ == "__main__":

    import sys
    import time
    from PyQt5.QtCore import QTimer, QCoreApplication
    from robot_manager import RobotManager

    # Create a Qt application (even without UI)
    app = QCoreApplication(sys.argv)

    try:
        robot = RobotManager()

        # Setup a timer to call `robot.where()` every 5 seconds
        timer = QTimer()
        timer.timeout.connect(robot.where)
        timer.start(5000)  # 5000ms = 5 seconds

        print("Robot test running... Press Ctrl+C to exit.")

        # Start Qt event loop (keeps script running)
        app.exec_()

    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        robot.close()
        print("Robot connection closed.")

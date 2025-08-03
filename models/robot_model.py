from PyQt5.QtCore import QObject, pyqtSignal, QTimer  # type: ignore
import yaml
import sys
import os
import time
import logging
from dataclasses import dataclass
from typing import Optional, Callable

# Add the parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.logger_config import get_logger
from models.robot_socket import RobotSocket

logger = get_logger("RobotModel")
with open('config.yml', 'r') as file:
    config = yaml.safe_load(file)

@dataclass
class CommandExpectation:
    expected_response: str
    timeout: float
    start_time: float
    on_success: Optional[Callable[[], None]] = None
    on_timeout: Optional[Callable[[], None]] = None

class RobotModel(QObject):
    """
    The RobotModel class manages robot communication, state, and status updates via a socket connection.

    Key responsibilities:
    - Maintains and reconnects socket connections to the physical robot
    - Sends commands and processes responses
    - Manages robot states (e.g., IDLE, IMAGING, INSERTING) based on responses
    - Tracks robot position (x, y, z, u) and queue status
    - Handles command expectations with optional success and timeout callbacks
    - Emits Qt signals for status, errors, and connection events
    - Periodically polls robot status and checks for timeouts

    The model uses a request-response pattern:
    1. Commands are sent via the socket
    2. Responses trigger state updates and signal emissions
    3. Timeouts are checked every 100ms; custom handlers are called if provided, otherwise a warning is logged

    Notes:
    - TODO items (e.g., starting with DISCONNECT state) exist but are not yet implemented
    """
    
    # Robot states
    DISCONNECT = 0
    IDLE = 1
    BUSY = 2
    EMERGENCY = 3

    # State names for logging
    STATE_NAMES = {
        0: "DISCONNECT",
        1: "IDLE",
        2: "BUSY",
        3: "EMERGENCY"
    }

    robot_connected = pyqtSignal()          # Emitted when connected
    robot_connection_error = pyqtSignal(str)
    robot_status = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, ip, port, timeout=5.0):
        super().__init__()
        self.ip = ip
        self.port = port
        self.socket = RobotSocket(ip, port, timeout)

        self.robot_state = self.DISCONNECT

        # Status tracking
        self.robot_x = 0.0
        self.robot_y = 0.0
        self.robot_z = 0.0
        self.robot_u = 0.0
        self.robot_queue_index = -1
        self.robot_queue_size = 0
        
        # Expectations management
        self._expectations = []  # List of CommandExpectation objects
        
        # Connect socket signals
        self.socket.connected.connect(self._on_connected)
        self.socket.connection_error.connect(self._on_connection_error)
        self.socket.response_received.connect(self._on_raw_response)
        
        # Setup reconnect timer
        self.reconnect_timer = QTimer()
        self.reconnect_timer.timeout.connect(self._attempt_reconnect)
        self.reconnect_timer.setInterval(3*1000) # Connect every 3s
        
        # Setup timeout checker
        self.timeout_timer = QTimer()
        self.timeout_timer.timeout.connect(self._check_timeouts)
        self.timeout_timer.start(100)  # Check every 100ms
    
    def connect_to_server(self):
        """Connect to the robot."""
        if self.socket.connect_to_server():
            # Stop reconnect timer when connected
            self.reconnect_timer.stop()
            return True
        else:
            self.robot_state = self.DISCONNECT
            # Start reconnect timer if not already running
            if not self.reconnect_timer.isActive():
                self.reconnect_timer.start()
            return False

    def _attempt_reconnect(self):
        """Attempt to reconnect to the robot if not connected."""
        if self.robot_state == self.DISCONNECT:
            logger.info("Attempting to reconnect to robot...")
            self.connect_to_server()

    def _on_connected(self):
        """Handle successful connection."""
        self.robot_state = self.IDLE
        self.robot_connected.emit()

    def _on_connection_error(self, error_msg):
        """Handle connection error."""
        self.robot_state = self.DISCONNECT
        self.robot_connection_error.emit(error_msg)
        # Start reconnect timer if not already running
        if not self.reconnect_timer.isActive():
            self.reconnect_timer.start()

    def _add_expectation(self, expected_response: str, timeout: float, 
                        on_success: Optional[Callable[[], None]] = None,
                        on_timeout: Optional[Callable[[], None]] = None) -> None:
        """Add an expectation to track with callbacks for success and timeout."""
        expectation = CommandExpectation(
            expected_response=expected_response,
            timeout=timeout,
            start_time=time.time(),
            on_success=on_success,
            on_timeout=on_timeout
        )
        self._expectations.append(expectation)
        logger.debug(f"🔔: {expected_response} (timeout: {timeout}s)")

    def _on_raw_response(self, resp: str):
        """Process raw responses from the socket and handle expectations."""
        # Handle expectations
        for exp in list(self._expectations):
            if resp == exp.expected_response:
                logger.debug(f"🔕: {exp.expected_response} (timeout: {exp.timeout}s)")
                self._expectations.remove(exp)
                if exp.on_success:
                    exp.on_success()  # Drive the state machine forward
                return
        
        # Process status response (status {state #}, {x}, {y}, {z}, {u}, {index}, {queue size})
        if resp.startswith("status "):
            parts = resp.split(",")
            if len(parts) >= 7:
                try:
                    # Parse state and position
                    self.robot_state = int(parts[0].split()[1])  # Get state from "status X"
                    self.robot_x = float(parts[1].strip())
                    self.robot_y = float(parts[2].strip())
                    self.robot_z = float(parts[3].strip())
                    self.robot_u = float(parts[4].strip())
                    self.robot_queue_index = int(parts[5].strip())
                    self.robot_queue_size = int(parts[6].strip())
                    
                    stat_builder = f'robot: {self.STATE_NAMES[self.robot_state]}, '
                    stat_builder += f'{self.where()}, '
                    stat_builder += f'{self.robot_queue_index}/{self.robot_queue_size}'
                    self.robot_status.emit(stat_builder)
                except (ValueError, IndexError) as e:
                    logger.error(f"Error parsing status response: {e}")
            else:
                logger.error(f"Invalid status response: {resp}")
        
        # Handle error responses
        elif resp.startswith("error") or resp == "taskfailed":
            logger.error(f"Command failed: {resp}")
            self.error.emit(f"Command failed: {resp}")

    def _check_timeouts(self):
        """Check for timed out expectations"""
        current_time = time.time()
        
        # Iterate over a copy of the list, as we might modify the original list
        for expectation in self._expectations[:]:
            if current_time - expectation.start_time > expectation.timeout:
                logger.error(f"Expectation timed out: {expectation.expected_response}")

                self._expectations.remove(expectation)
                
                if expectation.on_timeout:
                    expectation.on_timeout()
                else:
                    logger.warning("No timeout handler")
        
    def send(self, cmd, expect=None, timeout=5.0, on_success=None, on_timeout=None):
        """
        Send a command to the robot and set up an expectation for a response.
        
        Args:
            cmd (str): The command to send to the robot
            expect (str, optional): Expected response from the robot
            timeout (float, optional): Timeout in seconds for the expected response
            on_success (callable, optional): Callback when expected response is received
            on_timeout (callable, optional): Callback when timeout occurs
            
        Returns:
            bool: True if command was sent successfully, False otherwise
        """
        if self.robot_state == self.DISCONNECT:
            logger.error("Robot not connected")
            return False
            
        # Send the command
        success = self.socket.send_command(cmd)
        
        if not success:
            logger.error(f"Failed to send command: {cmd}")
            return False
            
        # If we expect a response, set up the expectation
        if expect:
            self._add_expectation(
                expected_response=expect,
                timeout=timeout,
                on_success=on_success,
                on_timeout=on_timeout
            )
            
        return True
    
    def close(self):
        """Close the connection to the robot."""
        logger.info("Closing robot connection")
        self.reconnect_timer.stop()  # Stop reconnect timer
        self.timeout_timer.stop()    # Stop timeout checker
        self.socket.close()
        self.robot_state = self.DISCONNECT

    def where(self, simple=True) -> str:
        return "TO IMPLEMENT"


if __name__ == "__main__":
    # connect to robot
    # Create QApplication and start event loop
    from PyQt5.QtWidgets import QApplication  # type: ignore
    import sys
    
    logger.setLevel(logging.DEBUG)
    

    
    TEST_MODE = "MOVE_P2P"

    

    if TEST_MODE == "MOVE_P2P":
        app = QApplication(sys.argv)
        robot = RobotModel("192.168.0.1", 8501)
        robot.connect_to_server()

        points = [
            (100, 420, 0, 45),
            (-100, 420, 0, -45)
        ]

        class PointCycler:
            def __init__(self):
                logger.info("PointCycler initialized")
                self.current_point = 0
                robot.robot_connected.connect(self.move_to_next_point)

            def move_to_next_point(self):
                x, y, z, u = points[self.current_point]
                success = robot.send(f"move {x} {y} {z} {u}", expect="POSITION_REACHED", timeout=10.0, 
                        on_success=self._on_move_success)
                if not success:
                    logger.error("Failed to send move command")
                    return

            def _on_move_success(self):
                self.current_point = (self.current_point + 1) % len(points)
                self.move_to_next_point()

        # Start the cycle
        cycler = PointCycler()
        cycler.move_to_next_point()
        
        sys.exit(app.exec_())
        
    elif TEST_MODE == "QUEUE":
        app = QApplication(sys.argv)
        robot = RobotModel("192.168.0.1", 8501)
        robot.connect_to_server()
        
        class QueueTest:
            EXPECT_QUEUE_APPENDED = "QUEUE_APPENDED"
            EXPECT_QUEUE_CLEARED = "QUEUE_CLEARED"
            
            def __init__(self):
                logger.info("QueueTest initialized")
                self.batch_number = 0
                self.total_batches = 5  # 5 batches of 10 coordinates = 50 total
                robot.robot_connected.connect(self.start_queue_test)
            
            def start_queue_test(self):
                logger.info("Starting queue test")
                self.batch_number = 0
                self.send_next_batch()
            
            def send_next_batch(self):
                if self.batch_number >= self.total_batches:
                    logger.info("All batches sent. Clearing queue.")
                    self.clear_queue()
                    return
                
                # Generate 10 coordinates for this batch
                batch_coords = []
                start_idx = self.batch_number * 10
                for i in range(10):
                    x = 100 + (start_idx + i) * 2  # Spread points out for visibility
                    y = 200
                    batch_coords.append((x, y))
                
                # Build the queue command with coordinates
                queue_cmd = "queue " + " ".join([f"{x:.2f} {y:.2f}" for x, y in batch_coords])
                
                logger.info(f"Sending batch {self.batch_number + 1}/{self.total_batches}")
                robot.send(
                    cmd=queue_cmd,
                    expect=self.EXPECT_QUEUE_APPENDED,
                    timeout=3.0,
                    on_success=lambda: self.on_batch_sent(),
                    on_timeout=lambda: logger.error(f"Timeout sending batch {self.batch_number + 1}")
                )
            
            def on_batch_sent(self):
                logger.info(f"Batch {self.batch_number + 1} sent successfully")
                self.batch_number += 1
                self.send_next_batch()

            def clear_queue(self):
                robot.send(
                    cmd="clearqueue",
                    expect=self.EXPECT_QUEUE_CLEARED,
                    timeout=3.0,
                    on_success=lambda: logger.info("Queue successfully cleared")
                )
        
        # Start the test
        queue_test = QueueTest()
        
        sys.exit(app.exec_())

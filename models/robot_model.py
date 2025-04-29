from PyQt5.QtCore import QObject, pyqtSignal, QTimer  # type: ignore
import yaml
import functools
import sys
import os
import time
import logging
from dataclasses import dataclass
from typing import Optional, Callable, List

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
    Model that handles robot control with a simplified state machine.
    Manages communication with the robot through a socket connection.
    Maintains synchronization between app state and robot state.

    TO AI Agent: no more offline mode, not to write any emit unless developer ask for it
    """
    
    # Robot states
    IDLE = 0
    IMAGING = 1
    INSERTING = 2
    
    # State names for logging
    STATE_NAMES = {
        0: "IDLE",
        1: "IMAGING",
        2: "INSERTING",
        3: "DISCONNECT",
        4: "EMERGENCY"
        # TODO: add disconnect state, and init with it
    }

    robot_connected = pyqtSignal()          # Emitted when connected
    robot_connection_error = pyqtSignal(str)
    robot_status = pyqtSignal(str)
    robot_op_state_changed = pyqtSignal(int)
    error = pyqtSignal(str)

    def __init__(self, ip, port, timeout=5.0):
        super().__init__()
        # Initialize state
        # TODO: should start with disconnect state

        # robot_op_state: state of the operation handled by the app
        # robot_state: robot state from robot peroidic status update
        self.robot_op_state = self.IDLE
        self.robot_state = self.IDLE
        self.is_connected = False
        self.ip = ip
        self.port = port
        
        # Position tracking
        self.robot_x = 0.0
        self.robot_y = 0.0
        self.robot_z = 0.0
        self.robot_u = 0.0
        
        # Queue tracking
        self.robot_queue_index = -1
        self.robot_queue_size = 0
        
        # Create socket for I/O only
        self.socket = RobotSocket(ip, port, timeout)
        
        # Expectations management
        self._expectations: List[CommandExpectation] = []
        
        # Connect socket signals
        self.socket.connected.connect(self._on_connected)
        self.socket.connection_error.connect(self._on_connection_error)
        self.socket.response_received.connect(self._on_raw_response)
        
        # Setup status polling timer
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(lambda: self.socket.send_command("status"))
        
        # Setup reconnect timer
        self.reconnect_timer = QTimer()
        self.reconnect_timer.timeout.connect(self._attempt_reconnect)
        self.reconnect_timer.setInterval(5000) # Connect every 5s
        
        # Setup timeout checker
        self.timeout_timer = QTimer()
        self.timeout_timer.timeout.connect(self._check_timeouts)
        self.timeout_timer.start(100)  # Check every 100ms
        
        # Try initial connection
        self.connect_to_server()
    
    def _attempt_reconnect(self):
        """Attempt to reconnect to the robot if not connected."""
        if not self.is_connected:
            logger.info("Attempting to reconnect to robot...")
            self.connect_to_server()
    
    def connect_to_server(self):
        """Connect to the robot."""
        if self.socket.connect_to_server():
            self.is_connected = True
            # Start status polling
            self.status_timer.start(1000)  # 1 second
            # Stop reconnect timer when connected
            self.reconnect_timer.stop()
            return True
        else:
            self.is_connected = False
            # Start reconnect timer if not already running
            if not self.reconnect_timer.isActive():
                self.reconnect_timer.start()
            return False
    
    def _on_connected(self):
        self.robot_connected.emit()

    def _on_connection_error(self, error_msg):
        """Handle connection error."""
        # logger.error(f"Connection error: {error_msg}")
        self.is_connected = False
        self.status_timer.stop()
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

    def _remove_expectation(self, expected_response: str) -> None:
        """Remove all expectations with the given expected response."""
        before_count = len(self._expectations)
        self._expectations = [
            expectation for expectation in self._expectations
            if expectation.expected_response != expected_response
        ]
        removed = before_count - len(self._expectations)
        if removed > 0:
            logger.debug(f"🔕: {expected_response}")

    def _on_raw_response(self, resp: str):
        """Process raw responses from the socket and handle expectations."""
        # Handle expectations
        for exp in list(self._expectations):
            if resp == exp.expected_response:
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
                    
                    stat_emit_str = f'robot: {self.STATE_NAMES[self.robot_state]}, '
                    stat_emit_str += f'{self.where()}, '
                    stat_emit_str += f'{self.robot_queue_index}/{self.robot_queue_size}'
                    self.robot_status.emit(stat_emit_str)
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
                    self._on_timeout(expectation.expected_response)
    
    def _on_timeout(self, expected_response: str):
        """Default timeout handler if no specific handler provided."""
        logger.error(f"Command timed out waiting for {expected_response}")
        self.error.emit(f"Timed out waiting for {expected_response}")
        
        # Update state based on which expectation timed out
        if expected_response == "task position_reached" and self.robot_op_state == self.IMAGING:
            self._set_robot_op_state(self.IDLE)
        elif (expected_response == "task queue_set" or expected_response == "task queue_completed") and self.robot_op_state == self.INSERTING:
            self._set_robot_op_state(self.IDLE)
        
    def _set_robot_op_state(self, state):
        """Update the app state."""
        if self.robot_op_state != state:
            # old_state = self.STATE_NAMES[self.robot_op_state]
            # new_state = self.STATE_NAMES[state]
            # Only log state changes at debug level (remove INFO-level logging)
            # logger.debug(f"App state changed from {old_state} to {new_state}")
            self.robot_op_state = state
            self.robot_op_state_changed.emit(state)
        else:
            # logger.debug(f"App state not changed: {self.STATE_NAMES[self.robot_op_state]}")
            pass
    
    def process_section(self, section, capture_only=False):
        """
        High-level method to process a section - moves to position, captures image.
        If capture_only is False, will also process and insert.

        
        self._set_op_state(OpState.CAPTURING)
self._add_expectation(
    "task position_reached",
    timeout=10,
    on_success=self._queue_after_capture
)
self.socket.send_command(f"capture {x} {y} {z} {u}")

def _queue_after_capture(self):
    self._set_op_state(OpState.QUEUEING)
    self._add_expectation(
        "task queue_set",
        timeout=3,
        on_success=self._insert_after_queue
    )
    self.socket.send_command(self._make_queue_command())

def _insert_after_queue(self):
    self._set_op_state(OpState.INSERTING)
    self._add_expectation(
        "task queue_completed",
        timeout=5*len(self.capture_positions),
        on_success=lambda: self._set_op_state(OpState.IDLE)
    )
    self.socket.send_command(f"xqt DoInsertAll 1")

        """
        if not self.is_connected:
            logger.error("Robot not connected")
            return False
        
        if self.robot_op_state != self.IDLE:
            logger.error(f"Cannot process section: robot is not idle")
            return False
        
        # TODO
    

    def stop(self):
        """
        Stop command - stop current operation.
        State MOVING or INSERTING -> IDLE # TODO: better state transition, implement stopping state
        """
        if not self.is_connected:
            logger.error("Robot not connected")
            return False
        
        if self.robot_op_state != self.INSERTING:
            logger.warning(f"robot_op_state is not inserting")
                    
        # Update state immediately to prevent further commands
        self._set_robot_op_state(self.IDLE)

        # When stop is sent, we no longer expect queue_completed
        self._remove_expectation("task queue_completed") # TODO: remove all expectation

        # Add expectation with callback
        self._add_expectation(
            expected_response="task queue_stopped",
            timeout=2
        )
        
        # Send command
        success = self.socket.send_command("stop")
        
        if not success:
            logger.error("Failed to send stop command")
            
        return success
    
    def close(self):
        """Close the connection to the robot."""
        logger.info("Closing robot connection")
        self.status_timer.stop()
        self.reconnect_timer.stop()  # Stop reconnect timer
        self.timeout_timer.stop()    # Stop timeout checker
        self.socket.close()
        self.is_connected = False

    def where(self, simple=True) -> str:
        """
        Get the current robot position
        TODO: receive position from socket
        """
        if simple:
            return f"({self.robot_x:.1f}, {self.robot_y:.1f}, {self.robot_z:.1f}, {self.robot_u:.1f})"
        else:
            return f"x: {self.robot_x}, y: {self.robot_y}, z: {self.robot_z}, u: {self.robot_u}"

if __name__ == "__main__":
    # connect to robot
    # Create QApplication and start event loop
    from PyQt5.QtWidgets import QApplication
    import sys
    
    # Set logger level to INFO
    logger.setLevel(logging.INFO)
    
    app = QApplication(sys.argv)
    robot = RobotModel("192.168.0.1", 8501)

    counter = 0
    move_timer = QTimer()
    def test_robot_move():
        global counter

        if counter % 2 == 0:
            if robot.capture(100, 420, 0, 0):
                counter += 1
        elif counter % 2 == 1:
            if robot.capture(-100, 420, 0, 0):
                counter += 1
        
    move_timer.timeout.connect(test_robot_move)
    move_timer.start(3000)  # Slower movement test, every 7 seconds
    
    sys.exit(app.exec_())

from PyQt5.QtCore import QObject, pyqtSignal, QTimer  # type: ignore
import yaml
import functools
import sys
import os
import time
import logging

# Add the parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.logger_config import get_logger
from models.robot_socket import RobotSocket

logger = get_logger("RobotModel")
with open('config.yml', 'r') as file:
    config = yaml.safe_load(file)

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
        self.robot_queue_index = 0
        self.robot_queue_size = 0
        
        # Create and configure socket
        self.socket = RobotSocket(ip, port, timeout)
        
        # Connect socket signals
        self.socket.connected.connect(self._on_connected)
        self.socket.response_received.connect(self._on_response_received)
        self.socket.connection_error.connect(self._on_connection_error)
        self.socket.command_timeout.connect(self._on_command_timeout)
        
        # Setup status polling timer (empty for now)
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(lambda: None)
        
        # Setup reconnect timer
        self.reconnect_timer = QTimer()
        self.reconnect_timer.timeout.connect(self._attempt_reconnect)
        self.reconnect_timer.setInterval(5000) # Connect every 5s
        
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
        logger.error(f"Connection error: {error_msg}")
        self.is_connected = False
        self.status_timer.stop()
        self.robot_connection_error.emit(error_msg)
        # Start reconnect timer if not already running
        if not self.reconnect_timer.isActive():
            self.reconnect_timer.start()
    
    def _check_mismatch(self):
        """Check for state mismatch when received status update"""
        if not self.is_connected:
            logger.warning("Robot is not connected")
        elif self.robot_state != self.robot_op_state:
            # Reduce log verbosity by filtering expected mismatches
            # Don't log when app is IDLE but robot is IMAGING - this is normal during movement
            if not (self.robot_op_state == self.IDLE and self.robot_state == self.IMAGING):
                logger.warning(f"State mismatch: App={self.STATE_NAMES[self.robot_op_state]}, Robot={self.STATE_NAMES[self.robot_state]}")

    def _on_command_timeout(self, command, expected_response):
        """Handle emitted command timeout."""
        logger.error(f"Command timed out: {command}, expected: {expected_response}")
        
        # Update state based on which expectation timed out
        # if current state is imaging, set to idle
        if expected_response == "task position_reached" and self.robot_op_state == self.IMAGING:
            self._set_robot_op_state(self.IDLE)
        # if current state is inserting, set to idle
        elif (expected_response == "task queue_set" or expected_response == "task queue_completed") and self.robot_op_state == self.INSERTING:
            self._set_robot_op_state(self.IDLE)
        else:
            logger.error(f"Unexpected timeout: {command}, expected: {expected_response}")
    
    def _on_response_received(self, response):
        """Process robot responses."""
        
        # Process status response (status {state #}, {x}, {y}, {z}, {u}, {index}, {queue size})
        if response.startswith("status "):

            parts = response.split(",")
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
                    
                    # timestamp = time.strftime("%H:%M:%S.") + str(int(time.time()*10) % 10)
                    # print(' ' * 100 + f'{timestamp} robot state: {self.STATE_NAMES[self.robot_state]}, {self.where()}')
                    self.robot_status.emit(f'robot: {self.STATE_NAMES[self.robot_state]}, {self.where()}')
                except (ValueError, IndexError) as e:
                    logger.error(f"Error parsing status response: {e}")
            else:
                logger.error(f"Invalid status response: {response}")

            self._check_mismatch()

        # Handle position reached notifications
        elif response == "task position_reached":
            logger.debug("Position reached")
            self._set_robot_op_state(self.IDLE)
        
        # Handle queue-related responses
        elif response == "task queue_set":
            logger.info("Queue set")
            # State remains INSERTING until queue is completed or stopped
            
        elif response == "task queue_completed":
            logger.info("Queue completed")
            self._set_robot_op_state(self.IDLE)
            
        elif response == "task queue_stopped":
            logger.info("Queue stopped")
            self._set_robot_op_state(self.IDLE)
            
        # Handle error responses
        elif response.startswith("error") or response == "taskfailed":
            logger.error(f"Command failed: {response}")
    
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
    
    def capture(self, x, y, z, u):
        """
        Capture command - move to position and prepare for imaging.
        Only allowed if current state is IDLE.
        """
        if self.robot_op_state != self.IDLE:
            logger.error(f"Cannot capture: robot is not idle")
            return False

        # Update state first to prevent race conditions
        self._set_robot_op_state(self.IMAGING)
        
        # Send command
        command = f"capture {x:.2f} {y:.2f} {z:.2f} {u:.2f}"
        success = self.socket.send_command(command)
        
        if not success:
            # Revert state on send failure
            self._set_robot_op_state(self.IDLE)
            logger.error(f"Failed to send capture command")
            
        return success
    
    def queue_points(self, points):
        """
        Queue command - set queue of points for insertion.
        Only allowed if current state is IDLE.
        Points should be a list of (x,y) tuples.
        """
        if self.robot_op_state != self.IDLE:
            logger.error(f"Cannot queue points: app state is not IDLE")
            return False

        if self.robot_state != self.IDLE:
            logger.error(f"Cannot queue points: robot state is not IDLE")
            return False

        # Update state first to prevent race conditions
        self._set_robot_op_state(self.INSERTING)

        if not points or len(points) == 0:
            logger.error("Cannot queue empty point list")
            return False
            
        # Format command: queue x1,y1,z1,u1,...,xn,yn,zn,un
        coords = []
        for point in points:
            if len(point) != 2:
                logger.error(f"Invalid point format: {point}")
                return False
            coords.extend([f"{coord:.2f}" for coord in point])
            
        command = "queue " + " ".join(coords)
        
        # Send command
        success = self.socket.send_command(command)
        
        if not success:
            # Revert state on send failure
            self._set_robot_op_state(self.IDLE)
            logger.error("Failed to send queue command")
            
        return success
    
    def stop(self):
        """
        Stop command - stop current operation.
        State 2 -> 0
        """
        if self.robot_op_state != self.INSERTING:
            logger.warning(f"Not inserting")
            return False
                    
        # Update state immediately to prevent further commands
        self._set_robot_op_state(self.IDLE)
        
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
        self.socket.close()
        self.is_connected = False

    def where(self) -> str:
        """
        Get the current robot position
        TODO: receive position from socket
        """
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

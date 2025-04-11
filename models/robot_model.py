from PyQt5.QtCore import QObject, pyqtSignal, QTimer  # type: ignore
import yaml
import functools

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
        2: "INSERTING"
    }
    
    def __init__(self, ip, port, timeout=5.0):
        super().__init__()
        # Initialize state
        self.app_state = self.IDLE
        self.robot_state = self.IDLE
        self.is_connected = False
        
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
        self.socket.response_received.connect(self._on_response_received)
        self.socket.connection_error.connect(self._on_connection_error)
        self.socket.command_timeout.connect(self._on_command_timeout)
        
        # Setup status polling timer (every 1 second)
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self._check_mismatch)
        
        # Try initial connection
        self.connect_to_server()
    
    def connect_to_server(self):
        """Connect to the robot."""
        if self.socket.connect_to_server():
            self.is_connected = True
            # Start status polling
            self.status_timer.start(1000)  # 1 second
            return True
        else:
            self.is_connected = False
            return False
    
    def _on_connection_error(self, error_msg):
        """Handle connection error."""
        logger.error(f"Connection error: {error_msg}")
        self.is_connected = False
        self.status_timer.stop()
    
    def _check_mismatch(self):
        """Check for state mismatch every second"""
        if not self.is_connected:
            logger.warning("Robot is not connected")
        elif self.robot_state != self.app_state:
            logger.warning(f"State mismatch: App={self.STATE_NAMES[self.app_state]}, Robot={self.STATE_NAMES[self.robot_state]}")

    def _on_command_timeout(self, command, expected_response):
        """Handle command timeout."""
        logger.error(f"Command timed out: {command}, expected: {expected_response}")
        
        # Update state based on which expectation timed out
        if expected_response == "task position_reached" and self.app_state == self.IMAGING:
            self._set_app_state(self.IDLE)
        elif (expected_response == "task queue_set" or expected_response == "task queue_completed") and self.app_state == self.INSERTING:
            self._set_app_state(self.IDLE)
    
    def _on_response_received(self, response):
        """Process robot responses."""
        logger.debug(f"Response received: {response}")
        
        # Process status response (status {state}, {x}, {y}, {z}, {u}, {index}, {queue size})
        if response.startswith("status "):
            parts = response.split(" ")
            if len(parts) >= 7:
                try:
                    # Parse state and position
                    self.robot_state = int(parts[1])
                    self.robot_x = float(parts[2])
                    self.robot_y = float(parts[3])
                    self.robot_z = float(parts[4])
                    self.robot_u = float(parts[5])
                    self.robot_queue_index = int(parts[6])
                    self.robot_queue_size = int(parts[7])
                        
                except (ValueError, IndexError) as e:
                    logger.error(f"Error parsing status response: {e}")
                    
        # Handle position reached notifications
        elif response == "task position_reached":
            logger.info("Position reached")
            self._set_app_state(self.IDLE)
        
        # Handle queue-related responses
        elif response == "task queue_set":
            logger.info("Queue set")
            # State remains INSERTING until queue is completed or stopped
            
        elif response == "task queue_completed":
            logger.info("Queue completed")
            self._set_app_state(self.IDLE)
            
        elif response == "task queue_stopped":
            logger.info("Queue stopped")
            self._set_app_state(self.IDLE)
            
        # Handle error responses
        elif response.startswith("error") or response == "taskfailed":
            logger.error(f"Command failed: {response}")
    
    def _set_app_state(self, state):
        """Update the app state and emit signal."""
        if self.app_state != state:
            old_state = self.STATE_NAMES[self.app_state]
            new_state = self.STATE_NAMES[state]
            logger.info(f"App state changed from {old_state} to {new_state}")
            self.app_state = state
        else:
            logger.warning(f"App state not changed: {self.STATE_NAMES[self.app_state]}")
    
    def capture(self, x, y, z, u):
        """
        Capture command - move to position and prepare for imaging.
        Only allowed if current state is IDLE.
        """
        if self.app_state != self.IDLE:
            logger.error(f"Cannot capture: robot is not idle")
            return False
            
        # Format command
        command = f"capture {x:.2f} {y:.2f} {z:.2f} {u:.2f}"
        
        # Update state first to prevent race conditions
        self._set_app_state(self.IMAGING)
        
        # Send command
        success = self.socket.send_command(command)
        
        if not success:
            # Revert state on send failure
            self._set_app_state(self.IDLE)
            logger.error(f"Failed to send capture command")
            
        return success
    
    def queue_points(self, points):
        """
        Queue command - set queue of points for insertion.
        Only allowed if current state is IDLE.
        Points should be a list of (x,y,z,u) tuples.
        """
        if self.app_state != self.IDLE:
            logger.error(f"Cannot queue points: app state is {self.STATE_NAMES[self.app_state]}")
            return False
            
        if not points or len(points) == 0:
            logger.error("Cannot queue empty point list")
            return False
            
        # Format command: queue x1,y1,z1,u1,...,xn,yn,zn,un
        coords = []
        for point in points:
            if len(point) != 4:
                logger.error(f"Invalid point format: {point}")
                return False
            coords.extend([f"{coord:.2f}" for coord in point])
            
        command = "queue " + ",".join(coords)
        
        # Update state first to prevent race conditions
        self._set_app_state(self.INSERTING)
        
        # Send command
        success = self.socket.send_command(command)
        
        if not success:
            # Revert state on send failure
            self._set_app_state(self.IDLE)
            logger.error("Failed to send queue command")
            
        return success
    
    def stop(self):
        """
        Stop command - stop current operation.
        State 2 -> 0
        """
        if self.app_state != self.INSERTING:
            logger.warning(f"Not inserting, cannot stop")
            return False
                    
        # Update state immediately to prevent further commands
        self._set_app_state(self.IDLE)
        
        # Send command
        success = self.socket.send_command("stop")
        
        if not success:
            logger.error("Failed to send stop command")
            
        return success
    
    def close(self):
        """Close the connection to the robot."""
        logger.info("Closing robot connection")
        self.status_timer.stop()
        self.socket.close()
        self.is_connected = False

    def where(self) -> bool:
        """
        Get the current robot position
        TODO: receive position from socket
        """
        return False

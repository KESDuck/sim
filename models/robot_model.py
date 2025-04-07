from PyQt5.QtCore import QObject, pyqtSignal
import yaml

from utils.logger_config import get_logger
from models.robot_socket import RobotSocket

logger = get_logger("RobotModel")
with open('config.yml', 'r') as file:
    config = yaml.safe_load(file)

class RobotModel(QObject):
    """
    Model that handles robot control.
    Manages communication with the robot through a socket connection.
    TODO: Needed to check if camera is at right position. Should return robot position as list of int
    """
    connected = pyqtSignal()
    command_completed = pyqtSignal(bool)  # Success/failure
    robot_state_changed = pyqtSignal(str)  # Current state of the robot
    
    # Robot states
    DISCONNECTED = "disconnected"
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    
    def __init__(self, ip, port, timeout=5.0):
        super().__init__()
        self.current_state = self.DISCONNECTED
        self.is_connected = False
        
        # Create and configure socket
        self.socket = RobotSocket(ip, port, timeout)
        
        # Connect socket signals
        self.socket.connected.connect(self._on_socket_connected)
        self.socket.command_completed.connect(self._on_command_completed)
        self.socket.connection_error.connect(self._on_connection_error)
        self.socket.response_received.connect(self._on_response_received)
    
    def connect_to_server(self):
        """Connect to the robot."""
        logger.info("Connecting to robot...")
        result = self.socket.connect_to_server()
        return result
    
    def _on_socket_connected(self):
        """Handle socket connection event."""
        self._set_state(self.IDLE)
        self.is_connected = True
        self.connected.emit()
    
    def _on_command_completed(self, success):
        """Handle command completion from socket."""
        self._set_state(self.IDLE)
        self.command_completed.emit(success)
    
    def _on_connection_error(self, error_msg):
        """Handle connection error."""
        logger.error(f"Connection error: {error_msg}")
        self._set_state(self.ERROR)
    
    def _on_response_received(self, response):
        """Process robot responses for state changes."""
        # Update robot state based on messages if needed
        pass
    
    def _set_state(self, state):
        """Update the robot state."""
        if self.current_state != state:
            self.current_state = state
            logger.info(f"Robot state changed to: {state}")
            self.robot_state_changed.emit(state)
    
    def send_command(self, command, timeout=None):
        """Send a command to the robot."""
        if self.current_state == self.BUSY:
            logger.warning("Robot is busy, command queued")
        
        self._set_state(self.BUSY)
        return self.socket.send_command(command, timeout)
    
    def stop(self) -> bool:
        """
        Stop the current robot operation
        """
        if not self.is_connected:
            logger.warning("Offline mode - stop command")
            return True  # Pretend success in offline mode

        command = "STOP"
        if self.socket.send_command(command):
            logger.info("Robot stopped successfully")
            return True
        else:
            logger.error("Stop command failed")
            return False
    
    def stop_all(self) -> bool:
        """
        Stop current operation and clear command queue
        """
        if not self.is_connected:
            logger.warning("Offline mode - stop_all command")
            return True  # Pretend success in offline mode

        # Clear any pending commands
        self.socket.clear_queue()
            
        # Send stop command
        return self.stop()
    
    def close(self):
        """Close the connection to the robot."""
        logger.info("Closing robot connection")
        self.socket.close()
        self.is_connected = False
        self._set_state(self.DISCONNECTED)

    def jump(self, x, y, z, u) -> bool:
        """
        Move robot to target position (x, y, z, u)
        """
        if not self.is_connected:
            logger.warning(f"Offline mode - jump to: {x:.2f}, {y:.2f}, {z:.2f}, {u:.2f}")
            return True  # Pretend success in offline mode

        command = f"JUMP,{x:.2f},{y:.2f},{z:.2f},{u:.2f}"
        if self.socket.send_command(command):
            logger.info(f"Jump to: {x:.2f}, {y:.2f}, {z:.2f}, {u:.2f}")
            return True
        else:
            logger.error(f"Jump failed to: {x:.2f}, {y:.2f}, {z:.2f}, {u:.2f}")
            return False

    def insert(self, x, y, z, u) -> bool:
        """
        Perform insertion at target position (x, y, z, u)
        """
        if not self.is_connected:
            logger.warning(f"Offline mode - insert at: {x:.2f}, {y:.2f}, {z:.2f}, {u:.2f}")
            return True  # Pretend success in offline mode

        command = f"INSERT,{x:.2f},{y:.2f},{z:.2f},{u:.2f}"
        if self.socket.send_command(command):
            logger.info(f"Insert at: {x:.2f}, {y:.2f}, {z:.2f}, {u:.2f}")
            return True
        else:
            logger.error(f"Insert failed at: {x:.2f}, {y:.2f}, {z:.2f}, {u:.2f}")
            return False

    def echo(self) -> bool:
        """
        Test connection with echo command
        """
        if not self.is_connected:
            logger.warning("Offline mode - echo test")
            return True  # Pretend success in offline mode

        command = "ECHO"
        if self.socket.send_command(command):
            logger.info("Echo successful")
            return True
        else:
            logger.error("Echo failed")
            return False 
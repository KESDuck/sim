from PyQt5.QtCore import QObject, pyqtSignal
import yaml
import functools

from utils.logger_config import get_logger
from models.robot_socket import RobotSocket

logger = get_logger("RobotModel")
with open('config.yml', 'r') as file:
    config = yaml.safe_load(file)

def offline_mode_safe(func):
    """Decorator to handle offline mode for robot commands.
    If robot is not connected, logs a warning and returns success."""
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self.is_connected:
            # Extract function name for better logging
            func_name = func.__name__
            
            # Create descriptive message based on function name or arguments
            if "jump" in func_name:
                arg_str = ', '.join(f"{arg:.2f}" for arg in args[:4]) if len(args) >= 4 else "position"
                msg = f"Offline mode - {func_name} to: {arg_str}"
            elif "move" in func_name or "capture" in func_name:
                arg_str = ', '.join(f"{arg:.2f}" for arg in args[:4]) if len(args) >= 4 else "position"
                msg = f"Offline mode - {func_name} to: {arg_str}"
            elif "queue" in func_name:
                count = len(args[0]) if args and isinstance(args[0], list) else "items"
                msg = f"Offline mode - {func_name} with {count}"
            else:
                msg = f"Offline mode - {func_name} command"
            
            logger.warning(msg)
            return True  # Pretend success in offline mode
        return func(self, *args, **kwargs)
    return wrapper

class RobotModel(QObject):
    """
    Model that handles robot control.
    Manages communication with the robot through a socket connection.
    Supports TcpControlV2 protocol with state management and queue functionality.
    """
    connected = pyqtSignal()
    command_completed = pyqtSignal(bool)  # Success/failure
    robot_state_changed = pyqtSignal(str)  # Current state of the robot
    position_reached = pyqtSignal(float, float, float, float)  # Signals when position is reached
    connection_error = pyqtSignal(str)  # Signal for connection errors
    robot_status = pyqtSignal(str)  # Signal for robot status messages
    
    # Robot states (match TcpControlV2 states)
    DISCONNECTED = "disconnected"
    IDLE = "idle"
    IMAGING = "imaging"
    INSERTING = "inserting"
    ERROR = "error"
    
    def __init__(self, ip, port, timeout=5.0):
        super().__init__()
        self.current_state = self.DISCONNECTED
        self.is_connected = False
        
        # Create and configure socket
        self.socket = RobotSocket(ip, port, timeout)
        
        # Current insertion progress tracking
        self.queue_size = 0
        self.current_index = 0
        
        # Connect socket signals
        self.socket.connected.connect(self._on_socket_connected)
        self.socket.command_completed.connect(self._on_command_completed)
        self.socket.connection_error.connect(self._on_connection_error)
        self.socket.response_received.connect(self._on_response_received)
        
        # Try initial connection
        self.connect_to_server()
    
    def connect_to_server(self):
        """Connect to the robot."""
        if self.socket.connect_to_server():
            self._set_state(self.IDLE)
            self.is_connected = True
            self.connected.emit()
            return True
        else:
            self._set_state(self.ERROR)
            self.is_connected = False
            return False
    
    def _on_socket_connected(self):
        """Handle socket connection event."""
        self._set_state(self.IDLE)
        self.is_connected = True
        self.connected.emit()
    
    def _on_command_completed(self, success):
        """Handle command completion from socket."""
        # Only update to IDLE if we're not in the middle of queue processing
        if self.current_state != self.INSERTING or not success:
            self._set_state(self.IDLE)
        self.command_completed.emit(success)
    
    def _on_connection_error(self, error_msg):
        """Handle connection error."""
        logger.error(f"Connection error: {error_msg}")
        self._set_state(self.ERROR)
        self.connection_error.emit(error_msg)
    
    def _on_response_received(self, response):
        """Process robot responses for state changes."""
        if response.startswith("status "):
            self.robot_status.emit(response)
            # Process status updates from robot
            status_parts = response.split(" ")
            if len(status_parts) >= 2:
                robot_status = status_parts[1]
                
                # Update queue progress if available
                if robot_status == "inserting" and len(status_parts) >= 3:
                    try:
                        progress_parts = status_parts[2].split("/")
                        self.current_index = int(progress_parts[0])
                        self.queue_size = int(progress_parts[1])
                        logger.debug(f"Queue progress: {self.current_index}/{self.queue_size}")
                    except (IndexError, ValueError):
                        pass
                
                # Update state based on robot status
                if robot_status == "idle":
                    self._set_state(self.IDLE)
                elif robot_status == "imaging":
                    self._set_state(self.IMAGING)
                elif robot_status == "inserting":
                    self._set_state(self.INSERTING)
                
        elif response.startswith("position X:"):
            # Handle position report
            try:
                # Parse position from format "position X:123.45 Y:67.89 Z:10.11 U:12.13"
                pos_str = response.replace("position ", "")
                pos_parts = pos_str.split(" ")
                x = float(pos_parts[0].split(":")[1])
                y = float(pos_parts[1].split(":")[1])
                z = float(pos_parts[2].split(":")[1])
                u = float(pos_parts[3].split(":")[1])
                self.position_reached.emit(x, y, z, u)
                logger.info(f"Robot position: ({x}, {y}, {z}, {u})")
                
            except (IndexError, ValueError) as e:
                logger.error(f"Error parsing position response: {e}")
        
        elif response == "position_reached":
            # Handle position reached notification
            logger.info("Target position reached")
        
        elif response == "queue_completed":
            # Handle queue completion
            logger.info("Queue processing completed")
            self.queue_size = 0
            self.current_index = 0
            self._set_state(self.IDLE)
    
    def _set_state(self, state):
        """Update the robot state."""
        if self.current_state != state:
            self.current_state = state
            logger.info(f"Robot state changed to: {state}")
            self.robot_state_changed.emit(state)
    
    def send_command(self, command, timeout=None):
        """Send a command to the robot."""
        return self.socket.send_command(command, timeout)
    
    @offline_mode_safe
    def stop(self) -> bool:
        """
        Stop the current robot operation
        """
        command = "stop"
        if self.socket.send_command(command):
            logger.info("Robot stopped successfully")
            # Reset queue status
            self.queue_size = 0
            self.current_index = 0
            return True
        else:
            logger.error("Stop command failed")
            return False
    
    def stop_all(self) -> bool:
        """
        Stop current operation and clear command queue
        """
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

    @offline_mode_safe
    def jump(self, x, y, z, u, jump_z=None) -> bool:
        """
        Move robot to target position (x, y, z, u) with optional jump height
        """
        if jump_z is not None:
            command = f"jump {x:.2f} {y:.2f} {z:.2f} {u:.2f} {jump_z:.2f}"
            log_msg = f"Jump to: {x:.2f}, {y:.2f}, {z:.2f}, {u:.2f} with height {jump_z:.2f}"
        else:
            command = f"jump {x:.2f} {y:.2f} {z:.2f} {u:.2f}"
            log_msg = f"Jump to: {x:.2f}, {y:.2f}, {z:.2f}, {u:.2f}"
            
        if self.socket.send_command(command):
            logger.info(log_msg)
            return True
        else:
            logger.error(f"Jump failed: {log_msg}")
            return False

    @offline_mode_safe
    def capture(self, x, y, z, u) -> bool:
        """
        Move to position and prepare for imaging
        """
        if self.current_state != self.IDLE:
            logger.error(f"Cannot capture: robot is {self.current_state}")
            return False
            
        command = f"capture {x:.2f} {y:.2f} {z:.2f} {u:.2f}"
        if self.socket.send_command(command):
            logger.info(f"Capturing at: {x:.2f}, {y:.2f}, {z:.2f}, {u:.2f}")
            self._set_state(self.IMAGING)
            return True
        else:
            logger.error(f"Capture failed at: {x:.2f}, {y:.2f}, {z:.2f}, {u:.2f}")
            return False

    @offline_mode_safe
    def where(self) -> bool:
        """
        Get the current robot position
        """
        if self.current_state != self.IDLE:
            logger.error(f"Cannot get position: robot is {self.current_state}")
            return False
            
        command = "where"
        if self.socket.send_command(command):
            logger.info("Getting robot position")
            return True
        else:
            logger.error("Failed to get robot position")
            return False

    @offline_mode_safe
    def queue_coordinates(self, coordinates) -> bool:
        """
        Queue a list of coordinates for sequential processing
        coordinates should be a list of (x,y,z,u) tuples
        """
        if self.current_state != self.IDLE:
            logger.error(f"Cannot queue: robot is {self.current_state}")
            return False
            
        if not coordinates:
            logger.error("Empty coordinate list provided")
            return False
            
        # Build command string: "queue x1 y1 z1 u1 x2 y2 z2 u2 ..."
        command = "queue"
        for coord in coordinates:
            if len(coord) != 4:
                logger.error(f"Invalid coordinate format: {coord}")
                return False
                
            x, y, z, u = coord
            command += f" {x:.2f} {y:.2f} {z:.2f} {u:.2f}"
            
        if self.socket.send_command(command):
            self.queue_size = len(coordinates)
            self.current_index = 0
            self._set_state(self.INSERTING)
            logger.info(f"Queued {len(coordinates)} coordinates for processing")
            return True
        else:
            logger.error("Failed to queue coordinates")
            return False

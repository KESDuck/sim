from PyQt5.QtNetwork import QTcpSocket
from PyQt5.QtCore import QObject, pyqtSignal, QTimer
from utils.logger_config import get_logger
from collections import deque
from typing import Optional, Callable, Dict, List

# Configure the logger
logger = get_logger("Socket")

class RobotSocket(QObject):
    connected = pyqtSignal()          # Emitted when connected
    response_received = pyqtSignal(str)  # Emitted when a response is received
    connection_error = pyqtSignal(str)   # Emitted on connection error
    command_completed = pyqtSignal(bool)  # Emitted when command completes (success/failure)

    def __init__(self, ip, port, timeout=5.0):
        super().__init__()
        self.ip = ip
        self.port = port
        self.timeout = timeout  # Timeout in seconds
        self.socket = QTcpSocket()
        self.reconnect_timer = QTimer()
        self.reconnect_timer.timeout.connect(self.try_connect)
        
        # Command queue and state
        self.command_queue = deque()
        self.current_command: Optional[str] = None
        self.is_processing = False
        
        # Response callbacks
        self._response_callbacks: Dict[str, List[Callable]] = {"*": []}

        # Connect socket signals
        self.socket.connected.connect(self._on_connected)
        self.socket.readyRead.connect(self._on_ready_read)
        self.socket.errorOccurred.connect(self._on_error)

    def connect_to_server(self):
        """Connect to the robot server."""
        try:
            # Abort any existing connection
            self.socket.abort()
            
            # Connect and wait for connection
            self.socket.connectToHost(self.ip, self.port)
            
            # Wait for connection with timeout
            if not self.socket.waitForConnected(int(self.timeout * 1000)):
                error_msg = self.socket.errorString()
                logger.error(f"Connection timeout: {error_msg}")
                self.connection_error.emit(error_msg)
                return False
                
            return True
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Connection error: {error_msg}")
            self.connection_error.emit(error_msg)
            return False

    def try_connect(self):
        """Attempt to reconnect to the server."""
        if self.socket.state() != QTcpSocket.ConnectedState:
            logger.info("Attempting to reconnect...")
            self.connect_to_server()

    def _on_connected(self):
        """Handle successful connection."""
        logger.info("Connected to the server.")
        self.connected.emit()
        if self.reconnect_timer.isActive():
            self.reconnect_timer.stop()
        # Process any queued commands
        self._process_next_command()

    def send_command(self, command, timeout_task=None):
        """Queue a command for sending."""
        if self.socket.state() != QTcpSocket.ConnectedState:
            logger.warning("Socket is not connected.")
            return False

        # Add command to queue
        self.command_queue.append((command, timeout_task))
        logger.info(f"Command queued: {command}")
        
        # Start processing if not already
        if not self.is_processing:
            self._process_next_command()
        return True

    def _process_next_command(self):
        """Process the next command in the queue."""
        if not self.command_queue or self.is_processing:
            return

        self.is_processing = True
        command, timeout_task = self.command_queue.popleft()
        self.current_command = command
        
        try:
            logger.info(f"Sending: {command}")
            self.socket.write((command + "\r\n").encode())
            self.socket.flush()
            
            # Set up response handling
            def on_response(response):
                if response == "taskdone":
                    self._command_completed(True, on_response)
                elif response == "taskfailed":
                    self._command_completed(False, on_response)
                elif response == "stopped":
                    logger.info("Task was stopped by stop command")
                    self._command_completed(False, on_response)
            
            self._response_callbacks["*"].append(on_response)
            
            # Set up timeout for task completion
            QTimer.singleShot(timeout_task or int(self.timeout * 1000), 
                            lambda: self._check_task_timeout(command, on_response))
            
        except Exception as e:
            logger.error(f"Error sending command '{command}': {e}")
            self._command_completed(False, on_response)

    def _check_task_timeout(self, command, callback):
        """Handle task completion timeout."""
        if self.current_command == command:
            logger.warning(f"Task completion timeout for command: {command}")
            # Remove callback before completing
            if callback in self._response_callbacks["*"]:
                self._response_callbacks["*"].remove(callback)
            self._command_completed(False, callback)

    def _command_completed(self, success, callback):
        """Handle command completion."""
        if callback in self._response_callbacks["*"]:
            self._response_callbacks["*"].remove(callback)
        self.is_processing = False
        self.current_command = None
        self.command_completed.emit(success)
        # Process next command if any
        self._process_next_command()

    def clear_queue(self):
        """Clear the command queue without affecting the current running command."""
        count = len(self.command_queue)
        self.command_queue.clear()
        logger.info(f"Cleared {count} commands from the queue")
        return count

    def close(self):
        """Close the connection."""
        if self.socket.state() == QTcpSocket.ConnectedState:
            logger.info("Closing connection...")
            self.socket.disconnectFromHost()
            self.command_queue.clear()
            self.is_processing = False
            self.current_command = None

    def _on_ready_read(self):
        """Handle incoming data from the robot."""
        while self.socket.canReadLine():
            response = self.socket.readLine().data().decode().strip()
            logger.info(f"Received: {response}")
            self.response_received.emit(response)
            
            # Call all registered callbacks
            for callback in self._response_callbacks["*"]:
                callback(response)

    def _on_error(self):
        """Handle connection errors."""
        error_message = self.socket.errorString()
        logger.error(f"Socket error: {error_message}")
        if not self.reconnect_timer.isActive():
            self.reconnect_timer.start(5000)  # retry every 5 seconds
        
        # Fail current command if any, but don't pass a callback
        self.is_processing = False
        self.current_command = None
        self.command_completed.emit(False)
        # Process next command if any
        self._process_next_command()

from PyQt5.QtNetwork import QTcpSocket  # type: ignore
from PyQt5.QtCore import QObject, pyqtSignal  # type: ignore
from utils.logger_config import get_logger
from typing import Optional

# Configure the logger
logger = get_logger("Socket")

class RobotSocket(QObject):
    connected = pyqtSignal()          # Emitted when connected
    connection_error = pyqtSignal(str)   # Emitted on connection error
    response_received = pyqtSignal(str)  # Emitted when a response is received

    def __init__(self, ip: str, port: int, timeout: float = 5.0):
        super().__init__()
        self.ip = ip
        self.port = port
        self.default_timeout = timeout
        self.socket = QTcpSocket()
        
        # Setup socket signals
        self.socket.connected.connect(self._on_connected)
        self.socket.readyRead.connect(self._on_ready_read)
        self.socket.errorOccurred.connect(self._on_error)

    def connect_to_server(self) -> bool:
        """Connect to the robot server asynchronously."""
        try:
            # Abort any existing connection
            self.socket.abort()
            
            # Connect asynchronously - will trigger connected or errorOccurred signals
            self.socket.connectToHost(self.ip, self.port)
            
            # Return immediately, don't wait
            logger.info(f"Connecting to {self.ip}:{self.port}...")
            
            # Return true to indicate connection attempt started successfully
            return True
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Connection error: {error_msg}")
            self.connection_error.emit(error_msg)
            return False

    def send_command(self, command: str) -> bool:
        """Send a command to the robot."""
        if self.socket.state() != QTcpSocket.ConnectedState:
            logger.warning("Socket is not connected.")
            return False

        try:
            # Send command
            self.socket.write((command + "\r\n").encode())
            self.socket.flush()
            logger.info(f"📤: {command}")
            return True
        except Exception as e:
            logger.error(f"Error sending command: {e}")
            return False

    def close(self):
        """Close the connection."""
        if self.socket.state() == QTcpSocket.ConnectedState:
            logger.info("Closing connection...")
            self.socket.disconnectFromHost()

    def _on_ready_read(self):
        """Handle incoming data from the robot."""
        while self.socket.canReadLine():
            response = self.socket.readLine().data().decode().strip()
            # Forward all responses to the model
            self.response_received.emit(response)

    def _on_connected(self):
        """Handle successful connection."""
        logger.info("Connected to the server.")
        self.connected.emit()

    def _on_error(self):
        """Handle connection errors."""
        error_message = self.socket.errorString()
        logger.error(f"Socket error: {error_message}")
        self.connection_error.emit(error_message)

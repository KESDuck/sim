from PyQt5.QtNetwork import QTcpSocket  # type: ignore
from PyQt5.QtCore import QObject, pyqtSignal, QTimer  # type: ignore
from utils.logger_config import get_logger
from collections import deque
from typing import Optional, Callable, Dict, List, Deque, Tuple
from dataclasses import dataclass
from time import time

# Configure the logger
logger = get_logger("Socket")

@dataclass
class CommandExpectation:
    command: str
    expected_response: str
    timeout: float
    start_time: float

class RobotSocket(QObject):
    connected = pyqtSignal()          # Emitted when connected
    connection_error = pyqtSignal(str)   # Emitted on connection error
    response_received = pyqtSignal(str)  # Emitted when a response is received
    command_timeout = pyqtSignal(str, str)  # Command, expected response that timed out

    def __init__(self, ip: str, port: int, timeout: float = 5.0):
        super().__init__()
        self.ip = ip
        self.port = port
        self.default_timeout = timeout
        self.socket = QTcpSocket()
        
        # expectations management
        self.pending_expectations: List[CommandExpectation] = []
        
        # Setup socket signals
        self.socket.connected.connect(self._on_connected)
        self.socket.readyRead.connect(self._on_ready_read)
        self.socket.errorOccurred.connect(self._on_error)
        
        # Setup timeout checker
        self.timeout_timer = QTimer()
        self.timeout_timer.timeout.connect(self._check_timeouts)
        self.timeout_timer.start(100)  # Check every 100ms

        # TODO: expectation for status update

    def connect_to_server(self) -> bool:
        """Connect to the robot server."""
        try:
            # Abort any existing connection
            self.socket.abort()
            
            # Connect and wait for connection
            self.socket.connectToHost(self.ip, self.port)
            
            # Wait for connection with timeout
            return self.socket.waitForConnected(int(self.default_timeout * 1000))
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Connection error: {error_msg}")
            self.connection_error.emit(error_msg)
            return False

    def send_command(self, command: str) -> bool:
        """Send a command to the robot and set up appropriate expectations."""
        if self.socket.state() != QTcpSocket.ConnectedState:
            logger.warning("Socket is not connected.")
            return False

        try:
            # Send command
            self.socket.write((command + "\r\n").encode())
            self.socket.flush()
            logger.info(f"Sent command: {command}")

            # Set up command expectations
            cmd_type = command.split()[0]
            if cmd_type == "capture":
                self._add_expectation("capture", "task position_reached", 10)
            elif cmd_type == "queue":
                self._add_expectation("queue", "task queue_set", 3)
                self._add_expectation("queue", "task queue_completed", 300)
            elif cmd_type == "stop":
                self._add_expectation("stop", "task queue_stopped", 1)
                # When stop is sent, we no longer expect queue_completed
                self._remove_expectation("task queue_completed")
            elif cmd_type == "status":
                # Status commands don't have expectations
                pass
            else:
                logger.warning(f"Unknown command: {command}")
                return False
            return True
        except Exception as e:
            logger.error(f"Error sending command: {e}")
            return False

    def close(self):
        """Close the connection."""
        self.timeout_timer.stop()
        if self.socket.state() == QTcpSocket.ConnectedState:
            logger.info("Closing connection...")
            self.socket.disconnectFromHost()
        self.pending_expectations.clear()

    def _add_expectation(self, command: str, expected_response: str, timeout: float) -> None:
        """Add a command expectation to track."""
        expectation = CommandExpectation(
            command=command,
            expected_response=expected_response,
            timeout=timeout,
            start_time=time()
        )
        self.pending_expectations.append(expectation)
        logger.debug(f"Added expectation: {expected_response} (timeout: {timeout}s)")

    def _remove_expectation(self, expected_response: str) -> None:
        """Remove all expectations with the given expected response."""
        before_count = len(self.pending_expectations)
        self.pending_expectations = [
            expectation for expectation in self.pending_expectations
            if expectation.expected_response != expected_response
        ]
        removed = before_count - len(self.pending_expectations)
        if removed > 0:
            logger.debug(f"Removed {removed} expectations for response: {expected_response}")

    def _check_timeouts(self):
        """Check for timed out expectations"""
        current_time = time()
        
        # Iterate over a copy of the list, as we might modify the original list
        for expectation in self.pending_expectations[:]:
            if current_time - expectation.start_time > expectation.timeout:
                logger.error(f"Command timed out: {expectation.command}, expected response: {expectation.expected_response}")
                self._remove_expectation(expectation.expected_response)
                self.command_timeout.emit(expectation.command, expectation.expected_response)
            # TODO: do not remove for status update

    def _on_ready_read(self):
        """Handle incoming data from the robot."""
        while self.socket.canReadLine():
            response = self.socket.readLine().data().decode().strip()

            # logger.info(f"Received: {response}")

            # Handle task completion responses
            if response in ["task position_reached", "task queue_set", "task queue_completed", "task queue_stopped"]:
                self._remove_expectation(response)
                # TODO: expectation for status update

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


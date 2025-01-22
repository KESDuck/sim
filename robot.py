import sys
from PyQt5.QtNetwork import QTcpSocket
from PyQt5.QtCore import QObject, pyqtSignal, QTimer
from logger_config import get_logger

# Configure the logger
logger = get_logger("Socket")

class RobotSocketClient(QObject):
    connected = pyqtSignal()          # Emitted when connected
    response_received = pyqtSignal(str)  # Emitted when a response is received
    connection_error = pyqtSignal(str)   # Emitted on connection error

    def __init__(self, ip, port):
        super().__init__()
        self.ip = ip
        self.port = port
        self.socket = QTcpSocket()
        self.reconnect_timer = QTimer()
        self.reconnect_timer.timeout.connect(self.try_connect)

        # Connect socket signals
        self.socket.connected.connect(self.on_connected)
        self.socket.readyRead.connect(self.on_ready_read) # message come in, readyRead is emitted, and triggers on_ready_read
        self.socket.errorOccurred.connect(self.on_error)

    def connect(self):
        """Connect to the robot server."""
        logger.info(f"Connecting to {self.ip}:{self.port}...")
        self.try_connect()
        # self.socket.connectToHost(self.ip, self.port)

    def try_connect(self):
        if self.socket.state() != QTcpSocket.ConnectedState:
            self.socket.abort()
            self.socket.connectToHost(self.ip, self.port)

    def on_connected(self):
        """Handle successful connection."""
        logger.info("Connected to the server.")
        self.connected.emit()
        if self.reconnect_timer.isActive():
            self.reconnect_timer.stop()

    def send_command(self, command, timeout_ack=1000, timeout_task=5000):
        """Send a command and wait for acknowledgment and task completion.
           Timeout in ms(0.001s)"""
        if self.socket.state() != QTcpSocket.ConnectedState:
            logger.warning("Socket is not connected.")
            return False

        try:
            logger.info(f"Sending: {command}")
            self.socket.write((command + "\r\n").encode())
            self.socket.flush()

            if not self._wait_for_message("ack", timeout_ack):
                logger.warning("Error: No 'ack' received.")
                return False

            if not self._wait_for_message("taskdone", timeout_task):
                logger.warning("Error: No 'taskdone' received.")
                return False

            return True

        except Exception as e:
            logger.error(f"Error sending command '{command}': {e}")
            return False

    def close(self):
        """Close the connection."""
        if self.socket.state() == QTcpSocket.ConnectedState:
            logger.info("Closing connection...")
            self.socket.disconnectFromHost()

    def _wait_for_message(self, expected_message, timeout):
        """Wait for a specific message from the robot."""
        from PyQt5.QtCore import QEventLoop, QTimer

        loop = QEventLoop()
        timer = QTimer()
        timer.setSingleShot(True)

        def on_timer_timeout():
            loop.quit()

        def on_message_received(message):
            if message == expected_message:
                timer.stop()
                loop.quit()

        timer.timeout.connect(on_timer_timeout)
        self.response_received.connect(on_message_received)

        timer.start(timeout)
        loop.exec()

        self.response_received.disconnect(on_message_received)
        timer.timeout.disconnect(on_timer_timeout)

        return not timer.isActive()

    def on_ready_read(self):
        """Handle incoming data from the robot."""
        while self.socket.canReadLine():
            response = self.socket.readLine().data().decode().strip()
            logger.info(f"Received: {response}")
            self.response_received.emit(response)

    def on_error(self):
        """Handle connection errors."""
        error_message = self.socket.errorString()
        logger.error(f"Connection error: {error_message}")
        if not self.reconnect_timer.isActive():
            self.reconnect_timer.start(5000) # retry every 5 seconds

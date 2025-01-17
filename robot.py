from PyQt5.QtNetwork import QTcpSocket
from PyQt5.QtCore import QObject, pyqtSignal
from logger_config import get_logger

# Configure the logger
logger = get_logger("Socket") 

class RobotSocketClient(QObject):
    message_sent = pyqtSignal(str)        # Signal emitted when a message is sent
    response_received = pyqtSignal(str)  # Signal emitted when a response is received
    connection_error = pyqtSignal(str)   # Signal emitted when a connection error occurs

    def __init__(self, ip, port):
        super().__init__()
        self.ip = ip
        self.port = port
        self.socket = QTcpSocket()

        # Connect signals from QTcpSocket
        self.socket.connected.connect(self.on_connected)
        self.socket.readyRead.connect(self.on_ready_read)
        self.socket.errorOccurred.connect(self.on_error)

        self.buffer = b''  # For handling received data

    def connect_socket(self):
        """Connect to the robot using QTcpSocket."""
        logger.info(f"Connecting to {self.ip}:{self.port}...")
        self.socket.connectToHost(self.ip, self.port)

    def send_message(self, message):
        """Send a message to the robot via the connected QTcpSocket."""
        if self.socket.state() == QTcpSocket.ConnectedState:
            logger.info(f"Sending: {message}")
            self.socket.write((str(message).encode()) + b"\r\n")
            self.message_sent.emit(message)  # Emit a signal that a message was sent
        else:
            logger.warning("Socket is not connected. Cannot send message.")

    def close_socket(self):
        """Close the QTcpSocket."""
        if self.socket.state() == QTcpSocket.ConnectedState:
            logger.info("Closing socket connection...")
            self.socket.disconnectFromHost()
            if self.socket.state() != QTcpSocket.UnconnectedState:
                self.socket.waitForDisconnected(3000)

    # Slots
    def on_connected(self):
        logger.info("Connected to the server.")

    def on_ready_read(self):
        """Handle incoming data."""
        self.buffer += self.socket.readAll().data()
        if b'\r\n' in self.buffer:  # Assume messages end with '\r\n'
            message, self.buffer = self.buffer.split(b'\r\n', 1)
            response = message.decode('utf-8')
            logger.info(f"Received response: {response}")
            self.response_received.emit(response)  # Emit the received response as a signal

    def on_error(self, socket_error):
        """Handle connection errors."""
        error_message = self.socket.errorString()
        logger.error(f"Connection error: {error_message}")
        self.connection_error.emit(error_message)  # Emit the error message as a signal

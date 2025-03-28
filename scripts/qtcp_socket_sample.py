from PyQt5.QtNetwork import QTcpSocket
from PyQt5.QtCore import QObject, QTimer

class Client(QObject):
    def __init__(self):
        super().__init__()
        self.socket = QTcpSocket()

        # Connect signals to slots
        self.socket.connected.connect(self.on_connected)
        self.socket.readyRead.connect(self.on_ready_read)
        self.socket.errorOccurred.connect(self.on_error)
        self.socket.stateChanged.connect(self.on_state_changed)

        # Timer for sending messages every 5 seconds
        self.timer = QTimer()
        self.timer.timeout.connect(self.send_message)

        # Start connecting (non-blocking)
        self.socket.connectToHost('192.168.0.1', 8501)

    def on_connected(self):
        print("Connected to server.")
        self.timer.start(5000)  # Start timer to send message every 5 seconds

    def send_message(self):
        if self.socket.state() == QTcpSocket.ConnectedState:
            print("Sending: hello")
            self.socket.write(b'hello\n')
            self.socket.flush()  # Ensure the message is sent immediately

    def on_ready_read(self):
        response = self.socket.readAll()
        print(f"Received: {response.data().decode()}")

    def on_error(self, socket_error):
        print(f"Connection error: {socket_error}")
        print(f"Error message: {self.socket.errorString()}")

    def on_state_changed(self, state):
        print(f"Socket state changed: {state}")
        # Handle reconnection if needed
        if state == QTcpSocket.UnconnectedState:
            print("Disconnected. Attempting to reconnect...")
            self.timer.stop()  # Stop sending messages if disconnected
            self.socket.connectToHost('127.0.0.1', 60666)

# Usage
from PyQt5.QtWidgets import QApplication
app = QApplication([])
client = Client()
app.exec_()

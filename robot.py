import socket

class RobotSocketClient:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.socket = None

    def connect_socket(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.settimeout(3)
        self.socket.connect((self.ip, self.port))

    def send_message(self, message):
        """Send a message to the robot via the connected socket."""
        print(f"Sending: {message}")
        if self.socket:
            try:
                # Send the message
                self.socket.send((str(message).encode()) + b"\r\n")
                
                # Receive the response
                response = self.socket.recv(1024)
                print(f"Received response: {response.decode('utf-8')}")
                return response
            except socket.error as e:
                print(f"Failed to send or receive message: {e}")
        else:
            print("Socket is not connected. Cannot send message.")

    def close_socket(self):
        if self.socket:
            self.socket.close()
            self.socket = None

import socket

def start_echo_server(host='127.0.0.1', port=60666):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.bind((host, port))  # Bind to the specified host and port
            server_socket.listen(5)          # Allow up to 5 queued connections
            print(f"Echo server is listening on {host}:{port}...")

            while True:
                conn, addr = server_socket.accept()  # Accept a client connection
                print(f"Connection established with {addr}")
                try:
                    with conn:
                        while True:
                            data = conn.recv(1024)  # Receive up to 1024 bytes
                            if not data:           # If no data, the client has disconnected
                                print("Client disconnected.")
                                break
                            print(f"Received: {data.decode().strip()}")
                            conn.sendall(data)  # Send the received data back to the client
                except Exception as e:
                    print(f"Error with client {addr}: {e}")
    except KeyboardInterrupt:
        print("\nServer is shutting down gracefully.")
    except Exception as e:
        print(f"Server error: {e}")

if __name__ == "__main__":
    start_echo_server()

"""
Test TCP Server for Client Communication Testing
===============================================

A configurable test server to simulate different communication scenarios:
- Normal: Sends 'ack' immediately, then 'taskdone' after 2 seconds
- timeout_ack: Simulates timeout by not sending 'ack' response
- timeout_taskdone: Sends 'ack' but never sends 'taskdone'
- Useful for testing client timeout handling and retry logic
- Supports multiple concurrent client connections
"""

import socket
import threading
import time

def handle_client(client_socket, scenario):
    """Handle a single client connection."""
    if scenario == "normal":
        # Simulate sending 'ack' and 'taskdone'
        print("[Server] Sending 'ack'")
        client_socket.sendall(b"ack\n")
        time.sleep(2)  # Simulate delay before task is complete
        print("[Server] Sending 'taskdone'")
        client_socket.sendall(b"taskdone\n")
    elif scenario == "timeout_ack":
        # Do nothing to simulate 'ack' timeout
        print("[Server] Simulating timeout for 'ack'")
        time.sleep(5)
    elif scenario == "timeout_taskdone":
        # Send 'ack' but no 'taskdone'
        print("[Server] Sending 'ack'")
        client_socket.sendall(b"ack\n")
        print("[Server] Simulating timeout for 'taskdone'")
        time.sleep(5)

    client_socket.close()
    print("[Server] Client connection closed.")

def start_server(scenario="normal"):
    """Start the test server."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 22345))
    server.listen(1)
    print(f"[Server] Listening on 127.0.0.1:22345 (Scenario: {scenario})")

    while True:
        client_socket, addr = server.accept()
        print(f"[Server] Connection accepted from {addr}")
        client_handler = threading.Thread(target=handle_client, args=(client_socket, scenario))
        client_handler.start()

if __name__ == "__main__":
    scenario = input("Enter test scenario (normal, timeout_ack, timeout_taskdone): ").strip()
    start_server(scenario)

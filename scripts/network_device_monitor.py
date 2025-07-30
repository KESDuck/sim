"""
Network Device Status Monitor
============================

Real-time network connectivity monitor for multiple devices:
- Monitors Robot, Camera, Macbook, and Dell devices on local network
- Uses async ping to check connectivity status every second
- Displays live status table with green/red indicators
- Maintains history of all ping results
- Press Ctrl+C to exit gracefully
"""

import asyncio
from ping3 import ping
from typing import List, Tuple, Dict
import os
import time
import signal

# Device mapping
DEVICES = {
    "192.168.0.1": "Robot",
    "192.168.0.2": "Camera",
    "192.168.0.7": "Macbook",
    "192.168.0.8": "Dell"
}

async def check_ip(ip: str) -> Tuple[str, bool]:
    try:
        response = await asyncio.to_thread(ping, ip, timeout=3)
        return ip, response is not None
    except:
        return ip, False

def print_table(results: List[Tuple[str, bool]], history: List[List[bool]]):
    # Print header
    header = "|".join(f"{DEVICES[ip]:^8}" for ip, _ in results)
    print(header)
    print("-" * len(header))
    
    # Print history
    for row in history:
        status_row = "|".join(f"{'🟢' if status else '🔴':^8}" for status in row)
        print(status_row)

async def main():
    ips = list(DEVICES.keys())
    
    # Keep all statuses
    history = []
    
    # Set up signal handler
    loop = asyncio.get_event_loop()
    stop = asyncio.Event()
    
    def handle_sigint():
        stop.set()
    
    loop.add_signal_handler(signal.SIGINT, handle_sigint)
    
    try:
        while not stop.is_set():
            # Run all pings concurrently
            results = await asyncio.gather(*[check_ip(ip) for ip in ips])
            
            # Add current status to history
            current_status = [status for _, status in results]
            history.append(current_status)
            
            # Clear screen and print table
            os.system('clear' if os.name == 'posix' else 'cls')
            print("Device Status Monitor (Ctrl+C to exit)\n")
            print_table(results, history)
            
            # Wait before next check
            await asyncio.sleep(1)
            
    except asyncio.CancelledError:
        pass
    finally:
        print("\nExiting...")

if __name__ == "__main__":
    asyncio.run(main()) 
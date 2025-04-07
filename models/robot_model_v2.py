import asyncio
from typing import Tuple, Optional, List, Dict, Any, Union
import yaml
from pathlib import Path
import time

from utils.logger_config import get_logger
from models.robot_socket_v2 import RobotCommunicator, CommandStatus

logger = get_logger("Robot")
with open('config.yml', 'r') as file:
    config = yaml.safe_load(file)

class RobotModel:
    """
    Model that handles robot control.
    Manages communication with the robot through an asynchronous connection.
    """
    def __init__(self):
        """
        Initialize the robot model.
        """
        # Default connection values if not specified in config
        robot_ip = config.get("robot", {}).get("ip", "127.0.0.1")
        robot_port = config.get("robot", {}).get("port", 8080)
        robot_timeout = config.get("robot", {}).get("timeout", 5.0)
        
        logger.info(f"Connecting to robot at {robot_ip}:{robot_port}")
        
        # Create the communicator
        self.communicator = RobotCommunicator(
            ip=robot_ip,
            port=robot_port,
            timeout=robot_timeout
        )
        
        # Only try to connect if we have valid connection info
        if robot_ip != "127.0.0.1":  # Not using localhost default
            # Setup the connection without blocking
            self.connected = False
            asyncio.create_task(self._connect_async())
        else:
            logger.warning("Using offline mode - no robot connection")
            self.connected = False
            
    async def _connect_async(self) -> None:
        """Internal method to connect asynchronously and update state."""
        self.connected = await self.communicator.connect()
        if not self.connected:
            logger.error("Socket failed to connect!")
        else:
            logger.info("Socket connected successfully!")

    async def jump(self, x: float, y: float, z: float, u: float) -> bool:
        """
        Asynchronously move robot to target position (x, y, z, u)
        
        Args:
            x: X coordinate
            y: Y coordinate
            z: Z coordinate
            u: U rotation
            
        Returns:
            True if successful, False otherwise
        """
        if not self.connected:
            logger.warning(f"Offline mode - jump to: {x:.2f}, {y:.2f}, {z:.2f}, {u:.2f}")
            return True  # Pretend success in offline mode

        result = await self.communicator.send_command("JUMP", x, y, z, u)
        if result.status == CommandStatus.SUCCESS:
            logger.info(f"Jump to: {x:.2f}, {y:.2f}, {z:.2f}, {u:.2f}")
            return True
        else:
            logger.error(f"Jump failed to: {x:.2f}, {y:.2f}, {z:.2f}, {u:.2f} - {result.error_message}")
            return False

    async def insert(self, x: float, y: float, z: float, u: float) -> bool:
        """
        Asynchronously perform insertion at target position (x, y, z, u)
        
        Args:
            x: X coordinate
            y: Y coordinate
            z: Z coordinate
            u: U rotation
            
        Returns:
            True if successful, False otherwise
        """
        if not self.connected:
            logger.warning(f"Offline mode - insert at: {x:.2f}, {y:.2f}, {z:.2f}, {u:.2f}")
            return True  # Pretend success in offline mode

        result = await self.communicator.send_command("INSERT", x, y, z, u)
        if result.status == CommandStatus.SUCCESS:
            logger.info(f"Insert at: {x:.2f}, {y:.2f}, {z:.2f}, {u:.2f}")
            return True
        else:
            logger.error(f"Insert failed at: {x:.2f}, {y:.2f}, {z:.2f}, {u:.2f} - {result.error_message}")
            return False

    async def echo(self) -> bool:
        """
        Asynchronously test connection with echo command
        
        Returns:
            True if successful, False otherwise
        """
        if not self.connected:
            logger.warning("Offline mode - echo test")
            return True  # Pretend success in offline mode

        result = await self.communicator.send_command("ECHO")
        if result.status == CommandStatus.SUCCESS:
            logger.info("Echo successful")
            return True
        else:
            logger.error(f"Echo failed - {result.error_message}")
            return False
            
    async def where(self) -> Optional[Tuple[float, float, float, float]]:
        """
        Asynchronously get current robot position
        
        Returns:
            Tuple of (x, y, z, u) if successful, None otherwise
        """
        if not self.connected:
            logger.warning("Offline mode - where command")
            return (0.0, 0.0, 0.0, 0.0)  # Mock position in offline mode

        result = await self.communicator.send_command("WHERE")
        if result.status == CommandStatus.SUCCESS:
            # Parse the response - this would need custom handling in the protocol
            # This is a placeholder for implementation
            logger.info("Got robot position")
            return (0.0, 0.0, 0.0, 0.0)  # Would extract actual position from response
        else:
            logger.error(f"Failed to get robot position - {result.error_message}")
            return None
            
    async def close(self) -> None:
        """
        Close socket connection
        """
        if self.connected:
            await self.communicator.close()
            self.connected = False
            logger.info("Socket connection closed")


if __name__ == "__main__":
    # Example usage of the async robot model with concurrency
    import asyncio
    
    async def robot_echo():
        robot = RobotModel()
        await asyncio.sleep(2)  # Allow connection to establish
        result = await robot.echo()
        print(f"Echo result: {result}")
        return result, robot
    
    async def robot_position_sequence(robot):
        """Execute a sequence of position commands concurrently"""
        # Define several positions to move to
        positions = [
            (100.0, 200.0, -50.0, 0.0),
            (150.0, 200.0, -50.0, 0.0),
            (150.0, 250.0, -50.0, 0.0),
            (100.0, 250.0, -50.0, 0.0)
        ]
        
        print("Starting position sequence...")
        # Execute jumps concurrently (gathered for waiting on completion)
        tasks = [robot.jump(*pos) for pos in positions]
        results = await asyncio.gather(*tasks)
        
        print(f"Position sequence results: {results}")
        return all(results)
    
    async def main():
        # First establish the connection
        echo_result, robot = await robot_echo()
        
        try:
            if echo_result:
                # Demonstrate concurrent command processing
                print("Starting concurrent operations...")
                
                # Run multiple operations concurrently
                task1 = asyncio.create_task(robot_position_sequence(robot))
                
                # While moving, we can do other things concurrently
                for i in range(5):
                    print(f"Concurrent operation: {i+1}")
                    await asyncio.sleep(0.5)
                
                # Wait for the position sequence to complete
                sequence_result = await task1
                print(f"Sequence completed: {sequence_result}")
        finally:
            # Always close the connection
            await robot.close()
            print("Connection closed")
    
    # Run the async main function
    asyncio.run(main())
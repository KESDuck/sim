import asyncio
import logging
from typing import Dict, Any, Optional, Callable, List, Union
from dataclasses import dataclass
from enum import Enum
from utils.logger_config import get_logger

# Configure the logger
logger = get_logger("RobotComm")

class CommandStatus(Enum):
    SUCCESS = "success"
    TIMEOUT = "timeout"
    ERROR = "error"

@dataclass
class CommandResult:
    status: CommandStatus
    command: str
    response: Optional[str] = None
    error_message: Optional[str] = None

class RobotCommandProtocol:
    """Defines the protocol for communicating with the robot."""
    
    def __init__(self):
        self.ACK_RESPONSE = "ack"
        self.TASK_DONE_RESPONSE = "taskdone"
        self.TASK_FAILED_RESPONSE = "taskfailed"
        self.LINE_ENDING = "\r\n"
    
    def format_command(self, command: str, *args) -> str:
        """Format a command with arguments according to the protocol."""
        if args:
            args_str = ",".join(f"{arg:.2f}" if isinstance(arg, float) else str(arg) for arg in args)
            return f"{command},{args_str}"
        return command
    
    def encode_command(self, command: str) -> bytes:
        """Encode a command for transmission."""
        return (command + self.LINE_ENDING).encode()
    
    def decode_response(self, data: bytes) -> str:
        """Decode a response from the robot."""
        return data.decode().strip()
    
    def is_ack(self, response: str) -> bool:
        """Check if a response is an acknowledgment."""
        return response == self.ACK_RESPONSE
    
    def is_task_done(self, response: str) -> bool:
        """Check if a response indicates task completion."""
        return response == self.TASK_DONE_RESPONSE
    
    def is_task_failed(self, response: str) -> bool:
        """Check if a response indicates task failure."""
        return response == self.TASK_FAILED_RESPONSE

class RobotCommunicator:
    """Handles communication with the robot using asyncio for non-blocking operations."""
    
    def __init__(self, ip: str, port: int, timeout: float = 5.0):
        self.ip = ip
        self.port = port
        self.timeout = timeout
        self.protocol = RobotCommandProtocol()
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.connected = False
        self.reconnect_delay = 5.0  # Seconds to wait before reconnection attempts
        self._connection_lock = asyncio.Lock()
        self._response_callbacks: Dict[str, List[Callable]] = {"*": []}

    async def connect(self) -> bool:
        """Connect to the robot server."""
        async with self._connection_lock:
            if self.connected:
                return True
                
            logger.info(f"Connecting to {self.ip}:{self.port}...")
            try:
                self.reader, self.writer = await asyncio.wait_for(
                    asyncio.open_connection(self.ip, self.port),
                    timeout=self.timeout
                )
                self.connected = True
                logger.info("Connected to the robot server.")
                
                # Start listening for responses in the background
                asyncio.create_task(self._listen_for_responses())
                return True
                
            except asyncio.TimeoutError:
                logger.error(f"Connection timed out after {self.timeout} seconds.")
                return False
                
            except (ConnectionRefusedError, OSError) as e:
                logger.error(f"Connection failed: {str(e)}")
                return False

    async def _listen_for_responses(self):
        """Background task to continuously read responses from the robot."""
        while self.connected and self.reader:
            try:
                data = await self.reader.readline()
                if not data:  # Connection closed
                    logger.warning("Connection closed by the server.")
                    await self._handle_disconnection()
                    break
                    
                response = self.protocol.decode_response(data)
                logger.info(f"Received: {response}")
                
                # Process callbacks for this response
                await self._process_response(response)
                
            except asyncio.CancelledError:
                logger.info("Response listener was cancelled.")
                break
                
            except Exception as e:
                logger.error(f"Error reading response: {str(e)}")
                await self._handle_disconnection()
                break

    async def _process_response(self, response: str):
        """Process incoming responses and notify relevant callbacks."""
        # Call all registered callbacks that match this response
        for pattern, callbacks in list(self._response_callbacks.items()):
            if pattern == response or (pattern == "*" and callbacks):
                for callback in callbacks[:]:  # Copy the list to avoid modification during iteration
                    try:
                        await callback(response)
                    except Exception as e:
                        logger.error(f"Error in response callback: {str(e)}")

    async def _handle_disconnection(self):
        """Handle unexpected disconnection."""
        self.connected = False
        if self.writer:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except Exception:
                pass  # Ignore errors during cleanup
                
        self.reader = None
        self.writer = None
        
        # Schedule reconnection attempt
        logger.info(f"Scheduling reconnection in {self.reconnect_delay} seconds.")
        await asyncio.sleep(self.reconnect_delay)
        asyncio.create_task(self.connect())

    async def send_command(self, command: str, *args, 
                          timeout_ack: Optional[float] = None, 
                          timeout_task: Optional[float] = None) -> CommandResult:
        """Send a command and wait for acknowledgment and task completion."""
        if not await self.ensure_connected():
            return CommandResult(
                status=CommandStatus.ERROR,
                command=command,
                error_message="Not connected to the robot server."
            )

        formatted_command = self.protocol.format_command(command, *args)
        
        # Default timeouts
        if timeout_ack is None:
            timeout_ack = 0.2  # 20% of timeout
        if timeout_task is None:
            timeout_task = self.timeout  # Full timeout

        logger.info(f"Sending: {formatted_command}")
        
        try:
            # Encode and send the command
            encoded_command = self.protocol.encode_command(formatted_command)
            if self.writer is None:
                return CommandResult(
                    status=CommandStatus.ERROR,
                    command=formatted_command,
                    error_message="Writer is not initialized."
                )
                
            self.writer.write(encoded_command)
            await self.writer.drain()
            
            # Wait for acknowledgment
            ack_future: asyncio.Future[bool] = asyncio.Future()
            
            async def on_ack_received(response):
                if self.protocol.is_ack(response) and not ack_future.done():
                    ack_future.set_result(True)
            
            # Register callback for acknowledgment
            self._response_callbacks["*"].append(on_ack_received)
            
            try:
                # Wait for acknowledgment with timeout
                await asyncio.wait_for(ack_future, timeout=timeout_ack)
            except asyncio.TimeoutError:
                logger.warning(f"Timeout waiting for acknowledgment after {timeout_ack} seconds.")
                return CommandResult(
                    status=CommandStatus.TIMEOUT,
                    command=formatted_command,
                    error_message="No acknowledgment received within timeout."
                )
            finally:
                # Remove callback
                if "*" in self._response_callbacks and on_ack_received in self._response_callbacks["*"]:
                    self._response_callbacks["*"].remove(on_ack_received)
            
            # Wait for task completion
            task_done_future: asyncio.Future[bool] = asyncio.Future()
            
            async def on_task_completion(response):
                if self.protocol.is_task_done(response) and not task_done_future.done():
                    task_done_future.set_result(True)
                elif self.protocol.is_task_failed(response) and not task_done_future.done():
                    task_done_future.set_exception(Exception("Task failed on the robot."))
            
            # Register callback for task completion
            self._response_callbacks["*"].append(on_task_completion)
            
            try:
                # Wait for task completion with timeout
                await asyncio.wait_for(task_done_future, timeout=timeout_task)
                return CommandResult(
                    status=CommandStatus.SUCCESS,
                    command=formatted_command,
                    response=self.protocol.TASK_DONE_RESPONSE
                )
            except asyncio.TimeoutError:
                logger.warning(f"Timeout waiting for task completion after {timeout_task} seconds.")
                return CommandResult(
                    status=CommandStatus.TIMEOUT,
                    command=formatted_command,
                    error_message="Task completion not received within timeout."
                )
            except Exception as e:
                logger.error(f"Task failed: {str(e)}")
                return CommandResult(
                    status=CommandStatus.ERROR,
                    command=formatted_command,
                    error_message=f"Task failed: {str(e)}"
                )
            finally:
                # Remove callback
                if "*" in self._response_callbacks and on_task_completion in self._response_callbacks["*"]:
                    self._response_callbacks["*"].remove(on_task_completion)
                    
        except Exception as e:
            logger.error(f"Error sending command: {str(e)}")
            return CommandResult(
                status=CommandStatus.ERROR,
                command=formatted_command,
                error_message=f"Failed to send command: {str(e)}"
            )

    async def ensure_connected(self) -> bool:
        """Ensure the connection is established."""
        if not self.connected:
            return await self.connect()
        return True

    async def close(self):
        """Close the connection."""
        if self.connected and self.writer:
            logger.info("Closing connection...")
            self.connected = False
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except Exception as e:
                logger.error(f"Error closing connection: {str(e)}")
            finally:
                self.reader = None
                self.writer = None

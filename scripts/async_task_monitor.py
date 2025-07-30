"""
Asyncio Task Monitoring Demo
===========================

Demonstrates how to monitor long-running async tasks in Python:
- Creates an async task that runs for 5 seconds
- Shows how to check task status while it's running
- Prints periodic status updates every second until completion
"""

import asyncio

async def long_running_task(task_id):
    print(f"[Task {task_id}] started...")
    await asyncio.sleep(5)
    print(f"[Task {task_id}] finished.")
    return f"Result of task {task_id}"

async def main():
    task = asyncio.create_task(long_running_task(1))
    
    while not task.done():
        print("[Main] Task is still running...")
        await asyncio.sleep(1)  # Check every second
    
    result = await task
    print(f"[Main] Task completed with result: {result}")

asyncio.run(main())
